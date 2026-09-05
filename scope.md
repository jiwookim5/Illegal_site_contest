# Scope — 신규 CVE 찾기 & 분석

## 분석 대상(In-Scope)

### 대상 선택 기준

- **오픈소스 소프트웨어**: GitHub, GitLab 등에서 공개된 소스
- **상용 소프트웨어**: 평가판/개발자 에디션으로 로컬 설치 가능
- **조건**:
  - 소스 코드에 접근 가능 (SAST 분석 가능)
  - 보안 취약점이 알려진 이력 있음 (유망한 대상)
  - 벤더가 책임 공개를 허용함 (정책 확인 필수)

### 테스트 환경

- **로컬 Docker 컨테이너**: 본인 제어 환경에서만
- **개발 머신**: 격리된 VM 또는 Docker
- **공개 인스턴스 테스트**: 원칙적으로 금지 (단, 벤더가 "버그바운티 환경"으로 명시한 경우만)

---

## Out of Scope (금지)

### 테스트 금지 대상

- 공개 프로덕션 인스턴스 (벤더 승인 없음)
- 다른 사용자의 데이터나 시스템
- 개인 정보 포함 데이터베이스

### 행동 제한

- **파괴적 행동**: 데이터 삭제, 설정 변경, 서비스 마비
- **지속성**: 웹셸, backdoor, persistence mechanism
- **Credential 수집**: 실제 벤더 API 키, DB 계정 등 (테스트용 만들기는 OK)
- **다른 사람 권리 침해**: 저작권, 라이선스 위반
- **무단 소스 배포**: 분석 대상의 소스 코드를 공개하지 않기 (보고는 OK)

---

## Safety 원칙

### 기본 규칙 (AGENTS.md 상속)

- **AI는 증거가 아니다**: 소스 리뷰 의견은 "발견 후보", 로컬 재현만 증거
- **검증 전까지 확정 금지**: PoC 없이는 "가능성" 수준
- **책임 공개**: 분석 후 벤더에 먼저 알리고 패치 기간 제공

### 이 프로젝트 추가 규칙

1. **로컬 환경만**: 모든 테스트는 Docker/VM 내에서
2. **벤더 정책 확인**: 버그바운티 프로그램이 있으면 규칙 준수
3. **Disclosure Timeline**: 
   - Day 0: 벤더에 비공개 리포트
   - Day 1-90: 벤더 응답/패치 대기 (기본 90일)
   - Day 91+: 공개 가능 (또는 합의 시 더 늦게)

---

## 현재 분석 대상

### 선택되지 않음 (PENDING)

아래 targets.md에서 후보를 선택하고, 벤더 정책 확인 후 GO 승인을 받아야 합니다.

---

## Scope 승인 상태

- **분석 대상**: PENDING (targets.md에서 선택 필요)
- **벤더 Disclosure 정책**: PENDING (매 대상마다 확인)
- **AI 작업 권한**: 대상이 확정되고 이 파일이 업데이트될 때만 진행

> targets.md의 대상이 선택되고, 해당 벤더의 책임 공개 정책이 확인된 후 Scope를 업데이트합니다.

---

## 참고

- CVE 공식 데이터베이스: https://cve.mitre.org
- CWE 분류: https://cwe.mitre.org
- 책임 있는 공개: https://cheatsheetseries.owasp.org/cheatsheets/Vulnerability_Disclosure_Cheat_Sheet.html
- CVSS Calculator: https://www.first.org/cvss/calculator/3.1
