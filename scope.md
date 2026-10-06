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

### Formbricks (github.com/formbricks/formbricks)

- **소스 코드**: 공개 (GitHub), TypeScript/Next.js, PostgreSQL
- **기존 보안 이력**: GHSA-7229-q9pv-j6p4 (Critical, JWT 서명 검증 누락) 1건. 그 외 공개 advisory 없음
- **벤더 Disclosure 정책** (2026-09-13 확인, `SECURITY.md` 원문 기준):
  - **접수 채널**: security@formbricks.com 이메일 전용 (공개 GitHub 이슈 금지)
  - **초기 응답**: 접수 후 48시간 이내
  - **패치 배포**: 심각도에 따라 7~28일
  - **버그바운티**: 없음 (금전 보상 일체 없음, 고정 정책)
  - **크레딧**: 요청 시 릴리즈 노트에 이름 공개, 익명 공개도 지원
  - **Legal Safe Harbor**: 정책을 따른 신고자에 대해 법적 조치를 취하지 않겠다고 명시
- **테스트 환경**: 로컬 Docker (`docker-compose.yml` 제공 여부는 Phase 1에서 재확인)

---

## 현재 분석 대상

### MediaCMS (github.com/mediacms-io/mediacms)

- **소스 코드**: 공개 (GitHub), Python(Django) + React, AGPL-3.0
- **기존 보안 이력**: GHSA-x3p4-4442-q2c3 (High, Remote Code Execution, 2024-11-08 공개) 1건. 그 외 공개 advisory 없음
- **벤더 Disclosure 정책** (2026-09-13 확인, `SECURITY.md` 원문 기준):
  - **접수 채널**: GitHub Security Advisories("Report a vulnerability")가 우선, 또는 https://mediacms.io/contact/ 문의 폼
  - **접수 확인**: 7일 이내
  - **해결**: 심각도에 따라 최대 90일 이내
  - **버그바운티**: 공식 프로그램 없음. 동의 시 릴리즈 노트/advisory에 크레딧
  - **Legal Safe Harbor**: ⚠️ **명시적 법적 안전조항 문구 없음.** 책임 공개 프로세스는 있으나 신고자에 대한 법적 불소추/면책 언급이 정책 문서에 없음 — Formbricks 대비 법적 리스크가 상대적으로 더 큼. 테스트는 반드시 로컬 환경에서만, 공개 인스턴스 접근 절대 금지 원칙을 더 엄격히 준수해야 함
- **테스트 환경**: `docker-compose.yaml` / `docker-compose-dev.yaml` / `docker-compose.full.yaml` 제공 확인됨

---

## 현재 분석 대상

### Documenso (github.com/documenso/documenso)

- **소스 코드**: 공개 (GitHub), TypeScript/Next.js, AGPL-3.0
- **기존 보안 이력**: 공개 GHSA **0건** — 상대적으로 덜 감사된 상태
- **벤더 Disclosure 정책** (2026-09-16 확인, `SECURITY.md` 원문 기준):
  - **접수 채널**: GitHub Security Advisories("Report a vulnerability")가 우선, 또는 security@documenso.com
  - **해결**: 최신 릴리스에만 보안 패치 적용 (버전 범위 정책 없음, 최신 버전 유지 요구)
  - **버그바운티**: 없음
  - **⚠️ 명시적 Out-of-Scope 목록 있음**: SSRF/DNS 리바인딩, Rate limiting/DoS, TLS·HTTP 보안 헤더·리버스 프록시 설정, 잘못된 자가 호스팅 배포 설정에 의존하는 발견은 **전부 접수 거부** — FreeScout류 SSRF 접근은 여기서 무의미하므로, 애플리케이션 로직/인가/문서·PDF 처리/웹훅 로직/인증 쪽에 집중해야 함
  - **Legal Safe Harbor**: 명시적 법적 안전조항 문구 없음 — 로컬 환경 원칙 엄격 준수
  - 자체적으로 Codex 기반 자동 보안 분석을 상시 운영 중이라고 명시 — 이미 발견된 이슈와 중복될 가능성 있음, 중복 확인 시 참고
- **테스트 환경**: 저장소 내 `docker/` 디렉터리 확인됨, docker-compose 기반 로컬 구동 예정

## 현재 분석 대상

### Baserow (github.com/baserow/baserow)

- **소스 코드**: 공개 (GitHub), Python(Django)+Vue, 코어(OSE)는 MIT — `premium/`, `enterprise/` 디렉터리는 별도 라이선스이므로 **분석/재현은 OSE(코어) 범위 우선, premium/enterprise 코드는 참고만 하고 라이선스 조건 별도 확인 필요**
- **기존 보안 이력**: 공개 GHSA **0건** — 상대적으로 덜 감사된 상태
- **벤더 Disclosure 정책** (2026-09-20 확인, `SECURITY.md` 원문 기준):
  - **접수 채널**: 이메일(bram@baserow.io)만 명시, 공식 프로세스/SLA/버그바운티 문구 없음
  - **Legal Safe Harbor**: 명시적 문구 없음 — 로컬 환경 원칙 엄격 준수
- **테스트 환경**: `docker-compose.yml` / `docker-compose.dev.yml` / `docker-compose.all-in-one.yml` 등 다수 확인됨
- **우선순위 검토 영역(예상)**: 워크스페이스/데이터베이스 권한 분리(IDOR), 수식(formula) 엔진(SSTI/인젝션 가능성), API 토큰 스코프, 웹훅, 스냅샷/임포트·익스포트 기능

## Scope 승인 상태

- **분석 대상**: **Baserow — SELECTED** (2026-09-20)
- **벤더 Disclosure 정책**: **확인 완료** (위 내용, 공식 프로세스 문서화 부재 유의)
- **AI 작업 권한**: 사용자 지시("알아서 서비스 선정하고 크리티컬한 취약점 찾기")로 Phase 1~3 진행 승인됨
- **이전 대상**:
  - Linkwarden — 2026-09-20 선정 → IDOR/DNS-리바인딩 SSRF(3개 경로)/SSO 계정연결 4개 영역 조사, 전부 이미 방어됨 확인(1건은 SAST 가설이었으나 DAST로 기각). 확정 취약점 0건, 하드닝 메모 1건. 상세: `6.Linkwarden/CVE_HUNT_SUMMARY.md`
  - Documenso — 2026-09-16 선정 → 2FA 백업코드 재사용 1건(CVSS 9.4/보수적 High) 확인, `research` 저장소 등록(PR #30, Campaign #31/Finding #32). 팀원 재검증 결과 추가 4건(관리자 비활성화 세션 잔존, presign 토큰 revocation 우회, 문서 가시성 ACL 우회, presign scope 우회) 확인 — 재검증 보고서 참고
  - Coolify — 2026-09-18 팀원 가설(Livewire cross-team IDOR) 교차검증 → **기각(REFUTED)**, 상세: `5.Coolify/CVE_HUNT_SUMMARY.md`
  - MediaCMS — 2026-09-13 선정 → `media_auth` X-Accel 인가 IDOR 1건 확인(CVSS 7.5 High), `research` 저장소에 등록(PR #24, Campaign #25/Finding #26), 팀 교차검수 대기 중. 벤더 미신고
  - Formbricks — 2026-09-08 선정 → 2026-09-13 종료, SAST 5개 영역에서 유의미한 취약점 미발견 (상세: `targets.md`, `analysis/source-code-audit/formbricks-findings.md`)
  - FreeScout — (scope.md 소급 미기록 상태였음, 2026-09-16 정리) SSRF TOCTOU(GHSA-qgjh-pmpj-85m6 제출 완료), bounce 이메일 HMAC 우회(미제출) 등 5건 확인. 상세: `analysis/source-code-audit/freescout-findings.md`

> 공개 프로덕션 인스턴스 테스트는 여전히 금지. 모든 재현은 로컬 Docker 환경에서만 수행.

---

## 참고

- CVE 공식 데이터베이스: https://cve.mitre.org
- CWE 분류: https://cwe.mitre.org
- 책임 있는 공개: https://cheatsheetseries.owasp.org/cheatsheets/Vulnerability_Disclosure_Cheat_Sheet.html
- CVSS Calculator: https://www.first.org/cvss/calculator/3.1
