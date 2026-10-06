# 불법광고 탐지 시스템 (Illegal Ad Detector)

정부 웹사이트에 숨겨진 불법광고(도박, 성인, 마약)를 자동으로 탐지하는 웹 크롤링 및 분석 시스템입니다.

## 🎯 주요 기능

### 1. 3단계 탐지 시스템
- **메인 페이지**: 직접 입력한 URL 분석
- **하위 페이지**: 같은 도메인 내부 링크 자동 크롤링 (depth ≤ 2)
- **외부 링크**: 페이지의 광고 링크 분석 + 리다이렉트 체인 추적

### 2. 정교한 키워드 기반 탐지
- 도박: 토토, 카지노, 바카라, 꽁머니 등 (90개 이상)
- 성인: 야동, 포르노, 성인물 등
- 마약: 대마, 코카인, 필로폰 등
- 점수 기반 판정: 60점 이상 탐지
- 컨텍스트 부스터: 근처 키워드로 신뢰도 증폭

### 3. 리다이렉트 추적
- HTTP 리다이렉트 체인 자동 추적 (최대 5단계)
- 의심스러운 크로스 도메인 리다이렉트 감지
- 최종 목적지에서 불법광고 탐지

### 4. 포탈 필터
- 학술 포털(KCI, RISS, Scholar) 자동 제외
- 뉴스 포털(Naver, Khan, Daum) 자동 제외
- 신뢰도 기반 스마트 필터

### 5. 탐지 위치 추적
- 어디에서 불법광고를 발견했는지 정확히 기록
- 형식: `메인페이지(키워드-신뢰도%) | 하위페이지:URL(키워드-신뢰도%) | 광고링크:도메인(키워드-신뢰도%)`
- CSV + JSON 듀얼 로깅

## 📊 기술 스택

- **Backend**: Flask, Python 3.14
- **Frontend**: HTML5, CSS3, JavaScript (Vanilla)
- **크롤링**: Selenium + Chrome WebDriver (JavaScript 렌더링)
- **파싱**: BeautifulSoup4
- **리다이렉트**: requests
- **로깅**: JSON (UI용) + CSV (감사 추적용)

## 🚀 설치 및 실행

### 1단계: 저장소 클론
```bash
git clone <repository-url>
cd tigerfish
```

### 2단계: 가상환경 생성
```bash
python3 -m venv venv
source venv/bin/activate  # macOS/Linux
# 또는
venv\Scripts\activate      # Windows
```

### 3단계: 의존성 설치
```bash
pip install -r requirements.txt
```

### 4단계: 애플리케이션 실행
```bash
python3 app.py
```

**웹 UI 접속**: http://localhost:8000

## 📱 사용 방법

### 웹 인터페이스
1. URL 입력 (예: `https://example.com`, `192.168.1.1`, `localhost:8080`)
2. "스캔" 버튼 클릭
3. 결과 확인

### 결과 확인
- **스캔 결과**: 메인 화면에서 바로 확인
- **기록 탭**: 과거 스캔 기록 조회
- **자세히 보기**: 모든 스캔 기록을 상세 HTML로 확인

### API
```bash
curl -X POST http://localhost:8000/api/scan \
  -H "Content-Type: application/json" \
  -d '{"ip": "https://example.com"}'
```

**응답 예시**:
```json
{
  "success": true,
  "detection": {
    "detected": true,
    "category": "도박",
    "keyword": "토토",
    "confidence": 100,
    "message": "🚨 [도박] '토토' 감지됨"
  },
  "internal_illegal_pages": [...],
  "linked_illegal_sites": [...]
}
```

## 🧪 테스트

### 테스트 서버 실행 (별도 터미널)
```bash
python3 test_redirect_server.py
```

### 테스트 시나리오
| URL | 설명 |
|-----|------|
| http://localhost:8888/test1 | 정상 페이지 (301 리다이렉트) |
| http://localhost:8888/test2 | 2단계 리다이렉트 |
| http://localhost:8888/test3 | 3단계 리다이렉트 체인 |
| http://localhost:8888/test-gambling | 불법광고 리다이렉트 (탐지 테스트) |

**테스트 방법**:
1. http://localhost:8000 접속
2. `http://localhost:8888/test-gambling` 입력
3. 불법광고 탐지 확인

## 📁 파일 구조

```
tigerfish/
├── app.py                      # Flask 백엔드 (주요 로직)
├── test_redirect_server.py    # 테스트용 리다이렉트 서버
├── requirements.txt            # 의존성 목록
├── templates/
│   └── index.html             # 웹 UI (React 없음, 순수 JavaScript)
├── scan_history.json          # 스캔 기록 (JSON, 최근 100개)
├── scan_log.csv               # 스캔 로그 (CSV, 영구 기록)
└── README.md                  # 문서
```

## 📊 로그 파일

### scan_history.json
- **목적**: UI 캐시, 빠른 조회
- **용량**: 최대 100개 기록 유지
- **형식**: JSON
```json
{
  "timestamp": "2026-10-06 19:01:50",
  "url": "http://localhost:8888/fake-casino",
  "detected": true,
  "category": "도박",
  "keyword": "토토",
  "confidence": 100,
  "detection_sources": "메인페이지(토토-100%) | 하위페이지:fake-casino(토토-100%)"
}
```

### scan_log.csv
- **목적**: 영구 감사 추적
- **용량**: 무제한 (모든 스캔 기록)
- **컬럼**: 11개 (시간, URL, 탐지, 카테고리, 키워드, 신뢰도, 도메인신뢰도, 하위페이지, 의심링크, 불법광고링크, 탐지위치)

## 🎓 탐지 신뢰도 해석

| 신뢰도 | 의미 | 예시 |
|--------|------|------|
| 95-100% | 확실 | 링크 목적지에서 실제 불법광고 확인 |
| 70-90% | 높음 | 페이지 + 광고 링크 분석 결과 |
| 50-70% | 의심 | 링크 패턴 + 도메인 분석 |
| <50% | 정보 | 저신뢰도 도메인 경고 |

## 🔧 문제 해결

### "Chrome not found" 오류
```bash
# webdriver-manager가 자동 설치하므로 보통 해결됨
pip install --upgrade webdriver-manager
```

### 포트 충돌 (Port already in use)
```bash
# macOS/Linux: 8000 포트 강제 종료
lsof -ti:8000 | xargs kill -9

# 테스트 서버도 동일 (8888 포트)
lsof -ti:8888 | xargs kill -9
```

### Selenium 타임아웃
- 네트워크 속도가 느린 경우 발생 가능
- app.py의 `WebDriverWait(driver, 10)` 값 증가

## 📝 라이센스

MIT License

## 👥 팀원 공유

이 프로젝트를 팀원들과 공유하려면:

1. **GitHub 저장소에 푸시**
   ```bash
   git add .
   git commit -m "Add detailed history view and detection sources tracking"
   git push origin cve-target-selection
   ```

2. **팀원들 설치**
   ```bash
   git clone <repository-url>
   cd tigerfish
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   python3 app.py
   ```

3. **테스트 (선택사항)**
   ```bash
   # 다른 터미널에서
   python3 test_redirect_server.py
   # http://localhost:8000 접속 → http://localhost:8888/test-gambling 테스트
   ```
