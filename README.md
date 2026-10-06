# 🚨 불법광고 탐지 시스템 (Illegal Ad Detector)

정부 웹사이트(공공기관, .go.kr)에 숨겨진 불법광고(도박, 성인, 마약)를 **자동으로 탐지**하는 IP 기반 웹 크롤링 & 분석 시스템입니다.

---

## 📋 주요 기능

### 1️⃣ **키워드 기반 탐지** (SAST)
- 페이지 텍스트에서 불법광고 키워드 검색
- 점수 기반 탐지: 도박(토토, 카지노, 바카라), 성인(야동, 포르노), 마약(대마, 코카인) 등
- 60점 이상 = 불법광고로 판정

### 2️⃣ **광고 링크 분석** (DAST)
- 페이지의 **모든 외부 링크** 추출
- 각 링크를 직접 방문하여 **실제 콘텐츠 확인**
- CTA 텍스트(입금, 보너스 등) + 도메인 패턴 분석
- 위험도 점수 계산

### 3️⃣ **리다이렉트 추적**
- HTTP 리다이렉트 체인 자동 추적
- 최종 URL에서 불법광고 탐지
- 의심스러운 리다이렉트 경고

### 4️⃣ **포탈 필터** (False Positive 제거)
- **학술 포털** (KCI, RISS, arXiv): 자동 제외
- **뉴스 포털** (Naver, Khan, Daum): 자동 제외
- 신뢰도 기반 필터 (70% 이상 도메인 보호)

---

## 🏗️ 기술 스택

| 항목 | 기술 |
|------|------|
| **Backend** | Flask 3.0 (Python) |
| **Frontend** | HTML/CSS/JavaScript (Vanilla) |
| **웹 크롤링** | Selenium + Chrome WebDriver |
| **HTML 파싱** | BeautifulSoup4 |
| **리다이렉트 추적** | requests 라이브러리 |
| **UI Framework** | CSS3 Grid/Flexbox (반응형) |

---

## 🚀 설치 & 실행

### 1️⃣ 가상환경 설정

```bash
cd tigerfish
python3 -m venv venv
source venv/bin/activate
```

### 2️⃣ 의존성 설치

```bash
pip install -r requirements.txt
```

### 3️⃣ 메인 앱 실행 (포트 8000)

```bash
python3 app.py
```

**웹 UI 접속:** http://localhost:8000

### 4️⃣ (선택) 테스트 서버 실행 (포트 8888)

리다이렉트 기능을 테스트하려면:

```bash
python3 test_redirect_server.py
```

**테스트 URL:**
- `http://localhost:8888/test1` → 단순 301 리다이렉트 (정상)
- `http://localhost:8888/test-gambling` → 카지노로 리다이렉트 (탐지 테스트)

---

## 📖 사용 방법

### 웹 UI

1. **URL 입력**: 정부 사이트 주소 또는 IP 입력
2. **스캔 클릭**: 분석 시작 (30초 타임아웃)
3. **결과 확인**:
   - ✅ 불법광고 없음
   - 🚨 불법광고 탐지 (카테고리, 신뢰도 표시)
   - 🔗 의심 광고 링크 (위험도, 이유)
   - 📍 리다이렉트 체인 (만약 있으면)

### API 사용

```bash
curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{"ip": "https://go.kr"}'
```

**응답:**
```json
{
  "success": true,
  "detection": {
    "detected": true,
    "category": "도박",
    "keyword": "카지노",
    "confidence": 95
  },
  "linked_illegal_sites": [
    {
      "original_url": "https://go.kr/page",
      "final_url": "https://casino.net",
      "redirect_chain": [...],
      "suspicious_redirect": true
    }
  ]
}
```

---

## 📊 탐지 신뢰도

| 수준 | 신뢰도 | 판단 기준 |
|------|--------|---------|
| 🚨 확실 | 95% | 링크 목적지에서 실제 불법광고 확인 |
| 🚨 높음 | 70-90% | 페이지 + 광고 링크 분석 |
| ⚠️ 의심 | 50-70% | 링크 패턴 (CTA + 도메인) |
| ℹ️ 정보 | <50% | 저신뢰도 도메인 경고 |

---

## 🧪 테스트 시나리오

### 테스트 1: 정상 페이지
```bash
# 입력: https://github.com
# 예상: ✅ 불법광고 없음
```

### 테스트 2: 학술 포털
```bash
# 입력: https://www.kci.go.kr/kciportal/ci/
# 예상: ✅ 학술 포털 - 탐지 무시
```

### 테스트 3: 뉴스 포털
```bash
# 입력: https://khan.co.kr
# 예상: ✅ 뉴스 포털 - 탐지 무시
```

### 테스트 4: 리다이렉트 (테스트 서버)
```bash
# 입력: http://localhost:8888/test-gambling
# 예상: 🚨 도박 탐지 + 리다이렉트 체인 표시
```

---

## 📁 파일 구조

```
tigerfish/
├── app.py                      # Flask 백엔드 (메인)
├── illegal_ad_detector.py      # 탐지 클래스 (MVP)
├── test_redirect_server.py     # 리다이렉트 테스트 서버
├── requirements.txt            # 의존성
├── templates/
│   └── index.html             # 웹 UI
├── README.md                  # 이 파일
├── .gitignore                 # Git 제외 파일
└── venv/                      # 가상환경 (Git 무시)
```

---

## 🔑 주요 함수

### 탐지 함수
- `detect_illegal_ads(text)` - 키워드 기반 탐지
- `extract_ad_links(html, domain)` - 광고 링크 추출
- `analyze_link_destination(link_url)` - 링크 목적지 분석
- `track_redirects(url)` - HTTP 리다이렉트 추적

### 필터 함수
- `is_academic_portal(url)` - 학술 포털 감지
- `is_news_portal(url)` - 뉴스 포털 감지
- `analyze_domain_trustworthiness(domain)` - 도메인 신뢰도 계산

### 크롤링
- `crawl_with_selenium(url)` - JavaScript 렌더링 포함 크롤링
- `extract_metadata(html)` - 메타데이터 추출

---

## ⚙️ 설정

### 탐지 키워드 (app.py)

**도박:**
```python
'토토': 95, '바카라': 85, '카지노': 80, ...
```

**성인:**
```python
'야동': 90, '포르노': 85, ...
```

**마약:**
```python
'대마': 90, '코카인': 85, ...
```

### CTA 패턴 (광고 링크)
```python
'입금': 25, '보너스': 20, '클릭': 15, ...
```

---

## 🚨 주의사항

1. **로컬 환경에서만 테스트** - 실제 불법 사이트 방문 X
2. **테스트 서버 사용** - `test_redirect_server.py`로 안전하게 검증
3. **타임아웃 설정** - 30초 (응답 없는 사이트 자동 건너뛰기)
4. **False Positive** - 학술/뉴스 포털 자동 필터링

---

## 📝 개선 사항 (향후)

- [ ] ML 기반 불법광고 분류 (더 정확한 탐지)
- [ ] 동적 키워드 업데이트 (새로운 용어 자동 추가)
- [ ] 데이터베이스 통합 (스캔 이력 저장)
- [ ] 배치 스캔 (대량 URL 동시 처리)
- [ ] 웹훅 연동 (자동 모니터링)
- [ ] 모바일 앱

---

## 📞 문의

**GitHub Issues:** https://github.com/jiwookim5/Illegal_site_contest/issues

---

## 📄 라이센스

MIT License - 교육 및 보안 연구 목적

---

**Created:** 2026-10-06  
**Version:** 1.0  
**Status:** ✅ Beta (기능 완성, 테스트 완료)
