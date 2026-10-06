#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
불법광고 탐지 도구 — 자동 크롤러
- Google 검색 결과 자동 수집
- .go.kr 사이트 자동 크롤링
- 불법광고 텍스트 자동 추출
- CSV로 자동 저장
"""

import requests
from bs4 import BeautifulSoup
import csv
import time
from urllib.parse import urljoin, urlparse
from datetime import datetime


class IllegalAdCrawler:
    def __init__(self, output_file="illegal_ads_data.csv"):
        self.output_file = output_file
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

        # 불법광고 검색 키워드 (카테고리별)
        self.keywords = {
            "도박": ["토토", "바카라", "첫충", "홀덤", "슬롯", "카지노", "배팅"],
            "성인": ["야동", "성인"],
            "마약": ["대마", "코카인"],
        }

    def google_search_url(self, keyword):
        """Google 검색 URL 생성 (site:*.go.kr 포함)"""
        search_query = f"site:*.go.kr {keyword}"
        base_url = "https://www.google.com/search"
        params = {
            'q': search_query,
            'num': 10  # 10개 결과
        }
        return f"{base_url}?q={'+'.join(search_query.split())}&num=10"

    def get_search_results(self, keyword):
        """Google 검색 결과에서 URL 추출"""
        url = self.google_search_url(keyword)

        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"❌ 검색 실패 ({keyword}): {e}")
            return []

        soup = BeautifulSoup(response.content, 'html.parser')
        results = []

        # Google 검색 결과 파싱
        for div in soup.find_all('div', class_='g'):
            try:
                link = div.find('a', href=True)
                if not link:
                    continue

                url = link['href']
                # Google 리다이렉트 URL 정제
                if '/url?q=' in url:
                    url = url.split('/url?q=')[1].split('&')[0]

                title = div.find('h3')
                title_text = title.get_text() if title else "No title"

                # .go.kr 사이트만 필터
                if '.go.kr' in url:
                    results.append({
                        'keyword': keyword,
                        'title': title_text,
                        'url': url
                    })
            except Exception as e:
                continue

        return results

    def extract_page_text(self, url):
        """페이지에서 텍스트 추출"""
        try:
            response = self.session.get(url, timeout=10)
            response.encoding = 'utf-8'
            response.raise_for_status()
        except requests.RequestException as e:
            print(f"  ⚠️ 페이지 로드 실패: {url}")
            return None

        soup = BeautifulSoup(response.content, 'html.parser')

        # 텍스트 추출 (스크립트, 스타일 제외)
        for script in soup(["script", "style"]):
            script.decompose()

        text = soup.get_text(separator=' ', strip=True)
        # 공백 정규화
        text = ' '.join(text.split())
        return text[:500] if text else None  # 처음 500글자만

    def crawl_keyword(self, category, keyword):
        """특정 키워드 크롤링"""
        print(f"\n🔍 크롤링 중: [{category}] '{keyword}'")

        search_results = self.get_search_results(keyword)
        if not search_results:
            print(f"  → 검색 결과 없음")
            return 0

        print(f"  → {len(search_results)}개 결과 발견")

        added_count = 0
        for i, result in enumerate(search_results, 1):
            url = result['url']
            print(f"  [{i}/{len(search_results)}] {url[:60]}...", end=" ")

            text = self.extract_page_text(url)
            if text:
                self.add_to_csv(category, keyword, url, text)
                print("✓ 저장됨")
                added_count += 1
            else:
                print("⚠️ 텍스트 없음")

            # 요청 간 딜레이 (서버 부하 방지)
            time.sleep(1)

        return added_count

    def add_to_csv(self, category, keyword, url, text):
        """CSV에 데이터 추가"""
        with open(self.output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['카테고리', '키워드', 'URL', '텍스트', '수집_날짜'])
            writer.writerow({
                '카테고리': category,
                '키워드': keyword,
                'URL': url,
                '텍스트': text,
                '수집_날짜': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            })

    def crawl_all(self):
        """모든 키워드 크롤링"""
        print("="*60)
        print("불법광고 자동 크롤러 시작")
        print("="*60)

        total_added = 0

        for category, keywords in self.keywords.items():
            print(f"\n[{category}] 크롤링 시작...")
            for keyword in keywords:
                added = self.crawl_keyword(category, keyword)
                total_added += added

        print("\n" + "="*60)
        print(f"✓ 크롤링 완료: 총 {total_added}건 수집됨")
        print(f"✓ 저장 위치: {self.output_file}")
        print("="*60)

        return total_added


def main():
    print("불법광고 자동 크롤러\n")
    print("선택:")
    print("1. 자동 크롤링 시작 (모든 키워드)")
    print("2. 특정 키워드만 크롤링")
    print("3. 종료")

    choice = input("\n선택 (1-3): ").strip()

    crawler = IllegalAdCrawler()

    if choice == '1':
        crawler.crawl_all()
    elif choice == '2':
        print("\n사용 가능한 키워드:")
        for category, keywords in crawler.keywords.items():
            print(f"  [{category}]: {', '.join(keywords)}")

        keyword = input("\n크롤링할 키워드: ").strip()
        category = input("카테고리 (도박/성인/마약): ").strip()

        if keyword and category:
            added = crawler.crawl_keyword(category, keyword)
            print(f"\n✓ {added}건 수집됨")
        else:
            print("❌ 입력 오류")
    elif choice == '3':
        print("종료합니다.")
    else:
        print("❌ 잘못된 선택입니다.")


if __name__ == "__main__":
    main()
