#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
IP 기반 불법광고 탐지 웹앱 서비스 (Selenium 기반)
URL을 입력하면 실제 브라우저로 렌더링하여 불법광고 탐지
"""

from flask import Flask, render_template, request, jsonify
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
from datetime import datetime
import re
import socket
import time

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False

# 불법광고 탐지 키워드 (카테고리별, 스코어 기반)
# 점수: 강도 (높을수록 명확한 불법광고)
KEYWORDS = {
    "도박": {
        # 극도로 명확한 키워드 (90-100점)
        "토토사이트": 95,
        "토토배팅": 95,
        "바카라사이트": 95,
        "온라인카지노": 95,

        # 명확한 키워드 (70-90점)
        "토토": 80,
        "바카라": 80,
        "카지노": 80,
        "홀덤": 75,
        "슬롯": 75,
        "첫충": 85,
        "꽁머니": 90,
        "꽁포": 90,
        "보너스머니": 85,
        "첫충보너스": 90,

        # 모호한 키워드 (40-70점, 컨텍스트 확인 필요)
        "배팅": 50,  # 스포츠 뉴스에도 나올 수 있음
        "베팅": 50,  # 스포츠 뉴스에도 나올 수 있음
        "라이브배팅": 75,
        "스포츠배팅": 65,
    },
    "성인": {
        "야동": 95,
        "야동사이트": 100,
        "포르노": 90,
        "포르노사이트": 100,
        "성인용품": 60,  # 정상 쇼핑도 있음
        "성인물": 95,
        "성인사이트": 100,
    },
    "마약": {
        "대마": 80,
        "대마초": 90,
        "코카인": 100,
        "필로폰": 95,
        "필로폰판매": 100,
        "마약": 90,
        "마약거래": 100,
        "히로뽕": 95,
    },
}

# 컨텍스트 강화 단어 (함께 나타나면 신뢰도 증가)
CONTEXT_BOOSTERS = {
    "가입": 15,      # "가입하기", "가입하면" 등
    "보너스": 20,    # "보너스", "무료", "선물" 등
    "입금": 25,      # "입금하면", "계좌" 등
    "지금": 10,      # "지금만", "지금 가입" 등
    "첫충": 25,      # "첫충 보너스" 등
    "꽁": 20,        # "꽁머니", "꽁" 등
}

# 신뢰도 높은 도메인 화이트리스트
WHITELIST_DOMAINS = {
    'naver.com': 85,
    'naver.co.kr': 85,
    'kin.naver.com': 85,
    'm.kin.naver.com': 85,
    'google.com': 85,
    'google.co.kr': 85,
    'github.com': 85,
    'stackoverflow.com': 85,
    'wikipedia.org': 85,
    'reddit.com': 80,
    'quora.com': 80,
    'youtube.com': 80,
    'facebook.com': 75,
    'twitter.com': 75,
    'instagram.com': 75,
}

# 제외 키워드 (이들이 포함되면 불법광고로 판정하지 않음)
EXCLUDE_PATTERNS = [
    "성인 교육",
    "성인용 학용품",
    "성인용 장비",
    "성인 대상",
    "다양한 계층을 대상으로",
    "어린이, 청소년, 성인",
    "성인용 물품",
    # Q&A 사이트 관련 표현
    "질문합니다",
    "질문해도",
    "도움말",
    "알려주세요",
    "지금은",
    "지금에",
    "물어보기",
    "문의합니다",
    "질문드립니다",
    "답변해주세요",
    "조언",
    "피드백",
    "경험 공유",
]

# 행동 기반 분석용 패턴
BEHAVIORAL_PATTERNS = {
    "긴급성_표현": ["지금", "지금만", "제한시간", "한정", "긴급", "서둘러"],
    "CTA_표현": ["문의하세요", "클릭", "연락", "신청", "가입", "참여"],
    "거래_신호": ["입금", "계좌", "계좌번호", "송금", "이체", "결제"],
    "신뢰_구축": ["100%", "보장", "안전", "검증", "인증", "후기"],
}

def normalize_url(url_input):
    """URL 정규화"""
    url = url_input.strip()

    # 프로토콜 제거
    if url.startswith('https://'):
        url = url[8:]
    elif url.startswith('http://'):
        url = url[7:]

    # 슬래시 제거
    url = url.rstrip('/')

    return url

def is_academic_portal(url):
    """학술 포털 감지 (패턴 기반)"""
    url_lower = url.lower()

    # 학술 포털 URL 패턴
    academic_patterns = [
        '/article/',      # 일반 학술 논문
        '/paper/',        # 논문
        '/ci/',           # KCI (Korean Citation Index)
        '/riss/',         # RISS
        '/dbpia/',        # DBPIA
        '/scholar/',      # Google Scholar
        '?sereArticleSearchBean.artiId=',  # KCI 논문 검색
        '/kciportal/',    # KCI 포털
        'scholar.google', # Google Scholar
        'arxiv.org',      # arXiv
        'researchgate',   # ResearchGate
        'academia.edu',   # Academia.edu
    ]

    for pattern in academic_patterns:
        if pattern in url_lower:
            return True

    return False

def is_news_portal(url):
    """뉴스 포탈 감지 (URL 패턴 기반)"""
    url_lower = url.lower()

    # 뉴스 포탈 URL 패턴
    news_patterns = [
        # DAUM
        'daum.net/v',        # DAUM 뉴스
        # Naver
        'naver.com/news',    # Naver 뉴스
        'naver.com/v',       # Naver 뉴스 (일부)
        'news.naver.com',    # Naver 뉴스
        # 주요 언론사
        'khan.co.kr',        # 경향신문
        'mk.co.kr',          # 매일경제
        'chosun.com',        # 조선일보
        'joongang.co.kr',    # 중앙일보
        'hankooki.com',      # 한국일보
        'donga.com',         # 동아일보
        'sportsseoul.com',   # 스포츠서울
        'seoul.co.kr',       # 서울신문
        'hankookilbo.com',   # 한국일보
        'inews24.com',       # 아이뉴스24
        'nocutnews.co.kr',   # 노컷뉴스
        # 뉴스 구독 서비스
        'news.google.com',   # Google 뉴스
        # URL 패턴
        '/news',             # 일반 뉴스 경로
        'biz.',              # 비즈니스 섹션
        'sport.',            # 스포츠 섹션
        'ent.'               # 엔터테인먼트 섹션
    ]

    for pattern in news_patterns:
        if pattern in url_lower:
            return True

    return False

def extract_ad_links(html, domain):
    """페이지에서 광고성 링크 추출"""
    from urllib.parse import urljoin, urlparse

    soup = BeautifulSoup(html, 'html.parser')
    ad_links = []

    for link in soup.find_all('a', href=True):
        href = link.get('href', '').strip()
        text = link.get_text(strip=True)[:50]  # 처음 50자만

        if not href or href.startswith('#') or href.startswith('javascript:'):
            continue

        # 절대 URL로 변환
        try:
            abs_url = urljoin(f"http://{domain}", href)
            link_domain = urlparse(abs_url).netloc
        except:
            continue

        # 외부 링크만 추출
        if link_domain and link_domain != domain:
            ad_links.append({
                'text': text,
                'href': abs_url,
                'domain': link_domain
            })

    return ad_links

def analyze_link_risk(link_text, link_domain):
    """링크의 위험도 점수 계산"""
    risk_score = 0
    risk_reasons = []

    # 1. CTA 텍스트 강도 분석
    cta_patterns = {
        '클릭': 15, '입금': 25, '참여': 20, '지금': 10,
        '가입': 15, '신청': 10, '시작': 10, '즉시': 10,
        '보너스': 20, '첫충': 25, '꽁머니': 25, '쿠폰': 15,
    }

    text_lower = link_text.lower()
    for pattern, score in cta_patterns.items():
        if pattern in text_lower:
            risk_score += score
            risk_reasons.append(f"CTA: {pattern}")

    # 2. 도메인 신뢰도 분석
    domain_trust = analyze_domain_trustworthiness(link_domain)

    if domain_trust < 40:
        risk_score += 25
        risk_reasons.append(f"낮은 신뢰도: {domain_trust}%")
    elif domain_trust < 60:
        risk_score += 15
        risk_reasons.append(f"중간 신뢰도: {domain_trust}%")

    # 3. 도메인 패턴 분석
    domain_lower = link_domain.lower()

    # 숫자가 많음
    digit_count = sum(1 for c in domain_lower if c.isdigit())
    hyphen_count = domain_lower.count('-')

    if digit_count >= 3:
        risk_score += 10
        risk_reasons.append("숫자 많음")

    if hyphen_count >= 2:
        risk_score += 10
        risk_reasons.append("하이픈 많음")

    # 서브도메인 깊음
    dot_count = domain_lower.count('.')
    if dot_count >= 3:
        risk_score += 10
        risk_reasons.append("깊은 서브도메인")

    return {
        'risk_score': min(risk_score, 100),
        'reasons': risk_reasons,
        'trust_score': domain_trust
    }

def track_redirects(url, timeout=5):
    """HTTP 리다이렉트 체인 추적"""
    try:
        import requests

        redirect_chain = []
        response = requests.head(url, allow_redirects=True, timeout=timeout, verify=False)

        # 리다이렉트 히스토리 기록
        for resp in response.history:
            redirect_chain.append({
                'status': resp.status_code,
                'url': resp.url
            })

        # 최종 URL 추가
        redirect_chain.append({
            'status': response.status_code,
            'url': response.url,
            'final': True
        })

        return redirect_chain
    except Exception as e:
        return []

def analyze_link_destination(link_url, timeout=5):
    """링크 목적지 크롤링 및 불법광고 탐지"""
    try:
        # 리다이렉트 체인 추적
        redirect_chain = track_redirects(link_url, timeout=2)

        # 최종 URL 결정
        final_url = redirect_chain[-1]['url'] if redirect_chain else link_url

        # 링크 목적지 크롤링 (최종 URL 사용)
        crawl_result, error = crawl_with_selenium(final_url, timeout=timeout)

        if error:
            return {
                'original_url': link_url,
                'final_url': final_url,
                'redirect_chain': redirect_chain,
                'reachable': False,
                'error': error,
                'detected': False
            }

        # 목적지의 텍스트에서 불법광고 탐지
        text = crawl_result['text']
        detection = detect_illegal_ads(text)

        # 리다이렉트가 의심스러운지 확인 (URL 도메인이 완전히 다른 경우)
        from urllib.parse import urlparse
        original_domain = urlparse(link_url).netloc
        final_domain = urlparse(final_url).netloc

        is_suspicious_redirect = (original_domain != final_domain) and len(redirect_chain) > 1

        return {
            'original_url': link_url,
            'final_url': final_url,
            'redirect_chain': redirect_chain,
            'suspicious_redirect': is_suspicious_redirect,
            'reachable': True,
            'detected': detection['detected'],
            'category': detection.get('category'),
            'keyword': detection.get('keyword'),
            'confidence': detection.get('confidence', 0),
            'text_sample': text[:200] if text else None
        }
    except Exception as e:
        return {
            'original_url': link_url,
            'reachable': False,
            'error': str(e),
            'detected': False
        }

def crawl_with_selenium(url_input, timeout=20):
    """고급 Selenium 크롤링 (메타데이터, HTML 구조 분석 포함)"""
    try:
        url = normalize_url(url_input)
        attempts = [f"https://{url}", f"http://{url}"]

        driver = None
        for attempt_url in attempts:
            try:
                options = webdriver.ChromeOptions()
                options.add_argument('--headless')
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                options.add_argument('--disable-gpu')
                options.add_argument('--window-size=1920,1080')
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                options.add_argument('user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36')
                options.add_argument('--ignore-certificate-errors')

                driver = webdriver.Chrome(
                    service=Service(ChromeDriverManager().install()),
                    options=options
                )

                driver.set_page_load_timeout(timeout)
                driver.get(attempt_url)

                # 페이지 로드 대기
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_all_elements_located((By.TAG_NAME, "body"))
                    )
                except:
                    pass

                # JavaScript 렌더링 완료 대기
                for _ in range(3):
                    driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(0.8)

                try:
                    WebDriverWait(driver, 5).until(
                        lambda d: d.execute_script("return document.readyState") == "complete"
                    )
                except:
                    pass

                # 최종 URL 캡처 (리다이렉트 감지)
                final_url = driver.current_url

                # HTML 추출
                html = driver.page_source
                soup = BeautifulSoup(html, 'html.parser')

                # 텍스트 추출 (종합)
                texts = []

                # 메인 텍스트
                for script in soup(["script", "style"]):
                    script.decompose()
                main_text = soup.get_text(separator=' ', strip=True)
                texts.append(main_text)

                # 메타데이터
                for meta in soup.find_all('meta'):
                    if meta.get('content'):
                        texts.append(meta.get('content'))

                # 제목
                title = soup.find('title')
                if title:
                    texts.append(title.get_text())

                # 링크 텍스트
                for link in soup.find_all('a'):
                    if link.get_text(strip=True):
                        texts.append(link.get_text(strip=True))

                # 버튼 텍스트
                for button in soup.find_all('button'):
                    if button.get_text(strip=True):
                        texts.append(button.get_text(strip=True))

                # 입력 필드 (placeholder 포함)
                for inp in soup.find_all('input'):
                    if inp.get('placeholder'):
                        texts.append(inp.get('placeholder'))

                # 모든 텍스트 합침
                full_text = ' '.join(texts)
                full_text = ' '.join(full_text.split())

                driver.quit()

                # 추가 분석 정보 반환
                analysis = {
                    'text': full_text[:3000] if full_text else '',
                    'html': html,
                    'url': final_url,  # 최종 URL (리다이렉트 후)
                    'requested_url': attempt_url,  # 원본 요청 URL
                    'metadata': extract_metadata(html)
                }

                return analysis, None

            except Exception as e:
                if driver:
                    try:
                        driver.quit()
                    except:
                        pass
                continue

        return None, "❌ 페이지 로드 실패"

    except Exception as e:
        return None, f"❌ 오류: {str(e)[:50]}"

def highlight_keyword(text, keyword):
    """텍스트에서 키워드를 강조"""
    import re
    # 대소문자 무시하고 키워드 강조
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    return pattern.sub(f'<mark style="background: #FFD700; font-weight: bold; padding: 2px 4px;">{keyword}</mark>', text)

def find_context_around_keyword(text, keyword, context_chars=100):
    """키워드 주변 문맥 추출"""
    import re
    pattern = re.compile(re.escape(keyword), re.IGNORECASE)
    match = pattern.search(text)

    if not match:
        return text[:200]

    start = max(0, match.start() - context_chars)
    end = min(len(text), match.end() + context_chars)

    context = text[start:end]

    # 시작/끝에 ... 추가
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""

    return prefix + context + suffix

def normalize_for_matching(text):
    """텍스트 정규화 (변형어 감지용)"""
    import re

    text = text.lower()

    # 여러 공백/탭 제거
    text = re.sub(r'\s+', '', text)

    # 특수문자 제거 (단어 사이의 특수문자)
    # 예: "토·토", "토_토", "토-토" → "토토"
    text = re.sub(r'[·_\-\.\!\@\#\$\%\^\&\*\(\)\[\]\{\}\|\\\/\:\;\'\"\<\>]', '', text)

    # 한글 자모 정규화 (예: ㅗ → o처럼 보이는 것들)
    # 한글 초성/중성/종성을 조합하는 경우 처리
    text = re.sub(r'ㅗ', 'o', text)
    text = re.sub(r'ㅣ', 'i', text)

    return text

def analyze_behavioral_signals(text):
    """행동 기반 분석 (CTA, 긴급성, 거래 신호 등)"""
    import re

    text_lower = text.lower()
    signals = {
        "긴급성": 0,
        "CTA": 0,
        "거래신호": 0,
        "신뢰구축": 0,
        "전화번호": 0,
        "카톡ID": 0,
    }

    # 각 카테고리별 신호 감지
    for pattern in BEHAVIORAL_PATTERNS.get("긴급성_표현", []):
        signals["긴급성"] += text_lower.count(pattern.lower())

    for pattern in BEHAVIORAL_PATTERNS.get("CTA_표현", []):
        signals["CTA"] += text_lower.count(pattern.lower())

    for pattern in BEHAVIORAL_PATTERNS.get("거래_신호", []):
        signals["거래신호"] += text_lower.count(pattern.lower())

    for pattern in BEHAVIORAL_PATTERNS.get("신뢰_구축", []):
        signals["신뢰구축"] += text_lower.count(pattern.lower())

    # 전화번호 감지 (010-1234-5678, 02-123-4567 등)
    if re.search(r'\d{2,3}[-]?\d{3,4}[-]?\d{4}', text):
        signals["전화번호"] = 1

    # 카톡 ID 감지 (문자와 숫자 조합)
    if re.search(r'[가-힣a-z0-9]{3,}(카톡|톡|카카오)', text_lower):
        signals["카톡ID"] = 1

    return signals

def calculate_behavior_score(signals):
    """행동 신호에서 의심도 점수 계산"""
    score = 0

    # 긴급성 + CTA + 거래신호 = 높은 의심도
    if signals["긴급성"] > 0 and signals["CTA"] > 0:
        score += 30

    if signals["거래신호"] > 0:
        score += 25

    if signals["전화번호"] > 0 or signals["카톡ID"] > 0:
        score += 20

    # 과도한 반복 (5회 이상) = 의심도
    if signals["긴급성"] >= 5:
        score += 15

    return min(score, 100)  # 최대 100점

def analyze_statistical_anomaly(text):
    """통계 기반 분석 (단어 빈도 이상 감지)"""
    import re

    words = text.lower().split()
    word_freq = {}

    # 단어 빈도 계산
    for word in words:
        word_clean = re.sub(r'[^\w가-힣]', '', word)
        if len(word_clean) > 2:  # 3글자 이상만
            word_freq[word_clean] = word_freq.get(word_clean, 0) + 1

    # 비정상 반복 감지
    max_freq = max(word_freq.values()) if word_freq else 0
    text_length = len(words)

    # 한 단어가 10% 이상 반복 = 비정상
    anomaly_score = 0
    if max_freq > text_length * 0.1:
        anomaly_score += 20

    # 단어 다양성 낮음 (고유단어 수 적음) = 비정상
    unique_ratio = len(word_freq) / max(text_length, 1)
    if unique_ratio < 0.3:  # 30% 미만
        anomaly_score += 15

    return min(anomaly_score, 100)

def analyze_domain_trustworthiness(url):
    """개선된 도메인 신뢰도 분석 (WHOIS 기반)"""
    trust_score = 50  # 기본값

    try:
        url_lower = url.lower()

        # 1단계: 화이트리스트 확인 (최우선)
        for whitelist_domain, score in WHITELIST_DOMAINS.items():
            if whitelist_domain in url_lower:
                return score

        # 2단계: TLD별 기본 신뢰도
        if '.go.kr' in url_lower:
            trust_score = 90
        elif '.edu.kr' in url_lower:
            trust_score = 85
        elif '.ac.kr' in url_lower:
            trust_score = 80
        elif '.or.kr' in url_lower:
            trust_score = 70
        elif '.co.kr' in url_lower:
            trust_score = 70  # 60% → 70% (언론사, 포탈 많음)
        elif url_lower.endswith(('.com', '.net', '.org', '.info')):
            trust_score = 40

        # 3단계: 도메인 나이 추정 (간단한 휴리스틱)
        # 숫자가 많으면 신생 도메인으로 추정
        digit_count = sum(1 for c in url_lower if c.isdigit())
        dash_count = url_lower.count('-')

        if digit_count >= 4:  # 숫자 4개 이상 = 신생 도메인
            trust_score -= 20
        elif digit_count >= 2:
            trust_score -= 10

        if dash_count > 2:  # 하이픈 많음 = 신생 도메인
            trust_score -= 10

        # 오래되어 보이는 도메인 (단순한 이름) = 신뢰도 +10
        # 예: naver.com, google.com, mk.co.kr 등
        domain_parts = url_lower.split('.')
        if len(domain_parts) >= 2:
            main_domain = domain_parts[0]
            # 짧고 간단한 이름 = 오래된 도메인
            if len(main_domain) <= 8 and main_domain.isalpha():
                trust_score += 10

    except:
        pass

    return max(trust_score, 10)


def extract_metadata(html):
    """메타데이터 추출 및 분석"""
    soup = BeautifulSoup(html, 'html.parser')
    metadata = {}

    # 제목
    title_tag = soup.find('title')
    metadata['title'] = title_tag.get_text() if title_tag else ''

    # 설명
    for meta in soup.find_all('meta'):
        if meta.get('name') == 'description':
            metadata['description'] = meta.get('content', '')
        elif meta.get('property') == 'og:description':
            metadata['og_description'] = meta.get('content', '')

    return metadata

def detect_morphed_keywords(text):
    """변형된 키워드 감지 (토·토, 토_토, 토ㅗㅇ 등)"""
    normalized = normalize_for_matching(text)

    for category, words in KEYWORDS.items():
        for word in words:
            normalized_word = normalize_for_matching(word)

            # 정규화된 텍스트에서 키워드 검색
            if normalized_word in normalized:
                return category, word

    return None, None

def is_false_positive(text, keyword):
    """거짓 양성 확인 (제외 패턴 체크)"""
    text_lower = text.lower()

    # 제외 패턴 확인
    for pattern in EXCLUDE_PATTERNS:
        if pattern.lower() in text_lower:
            return True

    return False

def detect_illegal_ads(text):
    """텍스트에서 불법광고 탐지 (다중 분석)"""
    if not text:
        return None

    text_lower = text.lower()

    # 1단계: 정상 키워드 탐지 (스코어 기반)
    best_detection = None
    highest_score = 0

    for category, words_dict in KEYWORDS.items():
        # words_dict는 {keyword: score} 형태
        for word, base_score in words_dict.items():
            if word.lower() in text_lower:
                # 거짓 양성 확인
                if is_false_positive(text, word):
                    continue

                # 컨텍스트 강화 계산
                context_boost = 0
                for booster_word, booster_score in CONTEXT_BOOSTERS.items():
                    if booster_word in text_lower:
                        keyword_pos = text_lower.find(word.lower())
                        booster_pos = text_lower.find(booster_word.lower())
                        if keyword_pos != -1 and booster_pos != -1:
                            if abs(keyword_pos - booster_pos) < 200:
                                context_boost += booster_score

                final_score = min(base_score + context_boost, 100)

                # 임계값 60점 이상만 탐지
                if final_score >= 60 and final_score > highest_score:
                    context = find_context_around_keyword(text, word, context_chars=150)
                    highlighted_context = highlight_keyword(context, word)

                    best_detection = {
                        'detected': True,
                        'category': category,
                        'keyword': word,
                        'message': f"🚨 [{category}] '{word}' 감지됨 (점수: {int(final_score)})",
                        'context': highlighted_context,
                        'found_text': context,
                        'detection_type': f'키워드 (점수: {int(final_score)})',
                        'confidence': int(final_score)
                    }
                    highest_score = final_score

    if best_detection:
        return best_detection

    # 2단계: 변형어 탐지
    category, morphed_word = detect_morphed_keywords(text)
    if category and morphed_word:
        if not is_false_positive(text, morphed_word):
            # 원본 키워드의 점수 사용 (변형어는 높은 신뢰도)
            base_score = KEYWORDS.get(category, {}).get(morphed_word, 80)

            # 컨텍스트 강화
            context_boost = 0
            for booster_word, booster_score in CONTEXT_BOOSTERS.items():
                if booster_word in text_lower:
                    keyword_pos = text_lower.find(morphed_word.lower())
                    booster_pos = text_lower.find(booster_word.lower())
                    if keyword_pos != -1 and booster_pos != -1:
                        if abs(keyword_pos - booster_pos) < 200:
                            context_boost += booster_score

            final_score = min(base_score + context_boost, 100)

            if final_score >= 60:
                context = find_context_around_keyword(text, morphed_word, context_chars=150)
                highlighted_context = highlight_keyword(context, morphed_word)

                return {
                    'detected': True,
                    'category': category,
                    'keyword': morphed_word,
                    'message': f"🚨 [{category}] '{morphed_word}' (변형어) 감지됨 (점수: {int(final_score)})",
                    'context': highlighted_context,
                    'found_text': context,
                    'detection_type': f'변형어 (점수: {int(final_score)})',
                    'confidence': int(final_score)
                }

    # 3단계: 행동 기반 분석 + 통계 분석 (키워드 없어도 탐지)
    behavioral_signals = analyze_behavioral_signals(text)
    behavior_score = calculate_behavior_score(behavioral_signals)
    statistical_score = analyze_statistical_anomaly(text)

    # 행동 신호가 강할 때 (임계값 상향: 50% → 65%)
    if behavior_score >= 65:
        # 신호 요약 생성
        signal_summary = []
        if behavioral_signals["긴급성"] > 0:
            signal_summary.append(f"긴급성 표현 {behavioral_signals['긴급성']}회")
        if behavioral_signals["CTA"] > 0:
            signal_summary.append(f"CTA 표현 {behavioral_signals['CTA']}회")
        if behavioral_signals["거래신호"] > 0:
            signal_summary.append(f"거래 신호 {behavioral_signals['거래신호']}회")
        if behavioral_signals["전화번호"]:
            signal_summary.append("전화번호 포함")
        if behavioral_signals["카톡ID"]:
            signal_summary.append("카톡 ID 포함")

        return {
            'detected': True,
            'category': '의심',
            'keyword': ', '.join(signal_summary),
            'message': f"⚠️ [의심 신호 탐지] 행동 기반 분석에서 불법광고 패턴 감지",
            'context': text[:300] + "..." if len(text) > 300 else text,
            'found_text': text[:300],
            'detection_type': '행동 기반 분석',
            'confidence': behavior_score,
            'behavioral_signals': behavioral_signals
        }

    # 통계 이상 감지 (신뢰도 낮은 사이트만)
    if statistical_score >= 35:
        # 신뢰도 70% 이상이면 통계 신호도 무시
        if True:  # domain_trust는 여기서 계산 안 되지만, 호출자에서 처리됨
            return {
                'detected': True,
                'category': '의심',
                'keyword': '비정상적인 단어 반복 또는 낮은 다양성',
                'message': f"⚠️ [의심 신호 탐지] 통계 분석에서 비정상 패턴 감지",
                'context': text[:300] + "..." if len(text) > 300 else text,
                'found_text': text[:300],
                'detection_type': '통계 기반 분석',
                'confidence': statistical_score
            }

    return {
        'detected': False,
        'category': None,
        'keyword': None,
        'message': "✅ 불법광고 없음",
        'context': None,
        'found_text': None,
        'detection_type': None,
        'confidence': 0
    }

@app.route('/')
def index():
    """메인 페이지"""
    return render_template('index.html')

@app.route('/api/scan', methods=['POST'])
def scan_ip():
    """고급 URL 스캔 API"""
    data = request.get_json()
    url_input = data.get('ip', '').strip()

    if not url_input:
        return jsonify({
            'success': False,
            'error': '❌ URL을 입력해주세요'
        }), 400

    # URL 크롤링 (메타데이터, HTML 분석 포함)
    crawl_result, error = crawl_with_selenium(url_input)

    if error:
        return jsonify({
            'success': False,
            'error': error,
            'url': normalize_url(url_input),
            'timestamp': datetime.now().isoformat()
        }), 400

    text = crawl_result['text']
    html = crawl_result['html']
    crawl_url = crawl_result['url']
    metadata = crawl_result['metadata']

    # 학술 포털 감지 (패턴 기반)
    is_academic = is_academic_portal(crawl_url)

    # 뉴스 포탈 감지 (패턴 기반)
    is_news = is_news_portal(crawl_url)

    # 불법광고 탐지 (학술/뉴스 포탈이면 무시)
    if is_academic or is_news:
        portal_type = "학술 포털" if is_academic else "뉴스 포탈"
        detection = {
            'detected': False,
            'category': None,
            'keyword': None,
            'message': f"✅ {portal_type} - 불법광고 탐지 무시",
            'context': None,
            'found_text': None,
            'detection_type': portal_type,
            'confidence': 0
        }
    else:
        detection = detect_illegal_ads(text)

    # 도메인 신뢰도 분석
    domain_trust = analyze_domain_trustworthiness(crawl_url)

    # 메타데이터에서도 불법광고 탐지 (학술/뉴스 포털 제외)
    if not is_academic and not is_news:
        metadata_text = ' '.join([str(v) for v in metadata.values() if v])
        if metadata_text:
            metadata_detection = detect_illegal_ads(metadata_text)
            # 메타데이터에서도 탐지되면 신뢰도 높임
            if metadata_detection['detected'] and not detection['detected']:
                detection = metadata_detection
                detection['detection_type'] = '메타데이터에서 탐지'

    # 광고 링크 분석 (학술/뉴스 포털 제외)
    risky_links = []
    linked_illegal_sites = []  # 목적지가 불법광고인 링크

    if not is_academic and not is_news and html:
        try:
            ad_links = extract_ad_links(html, normalize_url(crawl_url))

            for link in ad_links:
                link_risk = analyze_link_risk(link['text'], link['domain'])

                # 위험도 30 이상인 링크만 수집
                if link_risk['risk_score'] >= 30:
                    risky_links.append({
                        'text': link['text'],
                        'domain': link['domain'],
                        'risk_score': link_risk['risk_score'],
                        'reasons': link_risk['reasons'],
                        'trust_score': link_risk['trust_score']
                    })

            # 의심 링크의 목적지 분석 (모든 링크 체크)
            for link in ad_links:
                dest_analysis = analyze_link_destination(link['href'], timeout=30)

                # 불법광고 사이트로 확인된 링크만 기록
                if dest_analysis['detected']:
                    linked_illegal_sites.append({
                        'text': link['text'],
                        'domain': link['domain'],
                        'destination': dest_analysis['url'],
                        'category': dest_analysis.get('category'),
                        'keyword': dest_analysis.get('keyword'),
                        'confidence': dest_analysis.get('confidence', 0)
                    })

            # 불법광고 링크가 발견되면 높은 신뢰도로 탐지
            if linked_illegal_sites:
                detection['detected'] = True
                detection['category'] = linked_illegal_sites[0]['category']
                detection['keyword'] = f"{len(linked_illegal_sites)}개 불법광고 링크 연결"
                detection['detection_type'] = '불법광고 링크 목적지'
                detection['confidence'] = 95  # 실제 불법광고 확인 = 높은 신뢰도
                detection['message'] = f"🚨 {len(linked_illegal_sites)}개 불법광고 사이트 링크 탐지"
            # 의심 링크만 있으면 탐지 강도 낮춤
            elif risky_links and not detection['detected']:
                detection['detected'] = True
                detection['category'] = '의심'
                detection['keyword'] = f"{len(risky_links)}개 의심 광고 링크"
                detection['detection_type'] = '광고 링크 분석'
                detection['confidence'] = min(50 + (len(risky_links) * 10), 95)
                detection['message'] = f"🚨 {len(risky_links)}개 의심 광고 링크 탐지"
        except Exception as e:
            pass  # 링크 분석 실패는 조용히 무시

    # ⭐️ 신뢰도 >= 70% 이면 "의심" 신호 모두 무시 (신뢰도 높은 사이트 신뢰)
    if detection['detected'] and detection['category'] == '의심' and domain_trust >= 70:
        # 신뢰도 높은 도메인에서는 모든 의심 신호 무시
        detection = {
            'detected': False,
            'category': None,
            'keyword': None,
            'message': "✅ 불법광고 없음",
            'context': None,
            'found_text': None,
            'detection_type': None,
            'confidence': 0
        }

    # 최종 신뢰도 계산
    final_confidence = detection['confidence'] if detection['detected'] else 0

    # 도메인 신뢰도가 낮으면 경고 추가
    low_trust = domain_trust < 50

    return jsonify({
        'success': True,
        'url': crawl_url,
        'detection': detection,
        'domain_trust': domain_trust,
        'low_trust_warning': low_trust,
        'metadata': metadata,
        'risky_links': risky_links,
        'risky_links_count': len(risky_links),
        'linked_illegal_sites': linked_illegal_sites,
        'linked_illegal_sites_count': len(linked_illegal_sites),
        'text_sample': text[:500] + "..." if len(text) > 500 else text,
        'text_length': len(text),
        'timestamp': datetime.now().isoformat()
    })

@app.route('/api/keywords', methods=['GET'])
def get_keywords():
    """탐지 키워드 조회"""
    return jsonify(KEYWORDS)

if __name__ == '__main__':
    port = 8000
    print("\n" + "="*60)
    print("🚀 IP 기반 불법광고 탐지 웹앱 시작 (Selenium)")
    print("="*60)
    print(f"\n📱 접속 주소: http://localhost:{port}")
    print(f"📝 UI: 웹 브라우저에서 http://localhost:{port} 열기")
    print("\n💡 팁: URL만 입력하면 자동으로 HTTPS/HTTP 모두 시도합니다")
    print("="*60 + "\n")

    app.run(debug=False, host='0.0.0.0', port=port)
