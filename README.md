# Illegal Ad Detector

정부 웹사이트에 숨겨진 불법광고(도박, 성인, 마약)를 자동으로 탐지하는 웹 크롤링 및 분석 시스템입니다.

## 주요 기능

### 1. 키워드 기반 탐지
- 페이지 텍스트에서 불법광고 키워드 검색
- 도박(토토, 카지노, 바카라), 성인, 마약 등
- 점수 기반 판정: 60점 이상 탐지

### 2. 광고 링크 분석
- 페이지의 모든 외부 링크 추출
- 각 링크를 직접 방문하여 목적지 확인
- CTA 텍스트 + 도메인 패턴 분석

### 3. 리다이렉트 추적
- HTTP 리다이렉트 체인 자동 추적
- 최종 URL에서 불법광고 탐지
- 의심스러운 리다이렉트 경고

### 4. 포탈 필터
- 학술 포털(KCI, RISS) 자동 제외
- 뉴스 포털(Naver, Khan, Daum) 자동 제외
- 신뢰도 기반 필터(70% 이상 보호)

## 기술 스택

- Backend: Flask, Python
- Frontend: HTML, CSS, JavaScript
- 크롤링: Selenium + Chrome WebDriver
- HTML 파싱: BeautifulSoup4
- 리다이렉트: requests

## 설치

### 1. 가상환경 설정
```bash
python3 -m venv venv
source venv/bin/activate
```

### 2. 의존성 설치
```bash
pip install -r requirements.txt
```

### 3. 실행
```bash
python3 app.py
```

웹 UI: http://localhost:8000

## 사용 방법

### 웹 UI
1. URL 또는 IP 주소 입력
2. '스캔' 클릭
3. 결과 확인

### API
```bash
curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{"ip": "https://example.com"}'
```

## 테스트

### 테스트 서버 실행
```bash
python3 test_redirect_server.py
```

### 테스트 URL
- http://localhost:8888/test1 - 정상 페이지
- http://localhost:8888/test-gambling - 불법광고 (탐지 테스트)

## 파일 구조

```
tigerfish/
├── app.py                    - Flask 백엔드
├── illegal_ad_detector.py    - 탐지 클래스
├── test_redirect_server.py   - 테스트 서버
├── requirements.txt          - 의존성
├── templates/
│   └── index.html           - 웹 UI
└── README.md                - 문서
```

## 탐지 신뢰도

- 확실(95%): 링크 목적지에서 실제 불법광고 확인
- 높음(70-90%): 페이지 + 광고 링크 분석
- 의심(50-70%): 링크 패턴 분석
- 정보(<50%): 저신뢰도 도메인 경고

## 라이센스

MIT License
