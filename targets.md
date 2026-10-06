# 분석 대상 목록

> 이 문서는 실제 진행 상황을 반영한 최신 버전입니다.
> 최초 후보군 전체 목록은 [`real_targets.md`](./real_targets.md)를 참고하세요.

---

## 현재 분석 중

### Documenso

| 항목 | 내용 |
|---|---|
| **소프트웨어** | [Documenso](https://github.com/documenso/documenso) |
| **상태** | 🟢 IN PROGRESS — HIGH/Critical 후보 1건 로컬 재현 성공(FACT), 벤더 신고 대기 |
| **스타 수** | ~15,042 |
| **언어/스택** | TypeScript/Next.js(Remix), AGPL-3.0 |
| **선정일** | 2026-09-16 |
| **선정 사유** | 전자서명(법적 구속력 있는 문서) 처리 서비스라 공격 표면이 넓음 (PDF 처리, 웹훅, API 토큰, 인증/권한). 공개 GHSA 0건으로 상대적으로 덜 감사된 상태. 신고 절차 명확하나, **SSRF/DNS 리바인딩·Rate limiting/DoS·TLS 설정·배포 설정 의존 이슈는 명시적으로 접수 거부(out of scope)** — FreeScout류 SSRF 접근 재사용 불가, 애플리케이션 로직/인가/문서 처리 쪽에 집중 필요 |
| **로컬 재현 환경** | `docker/development/compose.yml`(db/redis/inbucket) + `npm run dev` (Remix). 커밋 `da934c0` 기준 구동 확인 |

#### 우선순위 검토 영역

- ~~문서/서명 워크플로우의 인가 로직~~ — SAST 완료(Explore agent), `getEnvelopeWhereInput` 중심으로 견고하게 방어됨. 확실한 IDOR 미발견
- ~~인증/토큰(2FA, 비밀번호 재설정, API 토큰, 조직 초대)~~ — SAST 완료, **2FA 백업 코드 재사용 결함 발견 → FACT로 승격**. 비밀번호 재설정/초대/공유링크 slug는 견고함 확인
- ~~PDF 업로드/웹훅~~ — SAST 완료. 웹훅 HMAC 미서명(Medium 후보, 미재현), presigned 업로드 PDF 검증 누락(영향 불명확), PDF DoS는 out-of-scope라 제외
- 남은 미검토: `disable-2fa`/`view-recovery-codes` 등 백업 코드 재사용 결함의 다른 소비 경로, admin-router 전반

#### 진행 상황

- [x] 코드베이스 구조 파악 (Phase 1)
- [x] SAST — Explore agent 3개 병렬 조사 (문서/인가, 인증/토큰, PDF/웹훅) — High 후보 1건, Medium 후보 1건
- [x] 후보 압축 — 2FA 백업 코드 재사용을 Phase 3 최우선 대상으로 선정
- [x] DAST — 로컬 재현 (Phase 3) — **동일 백업 코드로 독립된 완전 인증 세션 3/3 재현 성공, FACT로 승격** (`findings/documenso-2fa-backup-code-replay/`)
- [ ] 리포팅 & 벤더 신고 (Phase 4) — 미착수, 사용자 승인 필요

#### 확정된 발견 (FACT)

- **2FA 백업 코드 재사용 — 사용 후 무효화 안 됨 (CWE-294, CVSS 3.1 벡터상 9.4 Critical이나 전제조건 고려 시 보수적으로 High 권장)**:
  `verify-backup-code.ts`가 코드 포함 여부만 확인하고 소모(제거) 처리를 하지 않음. 로컬 dev에서
  동일 백업 코드로 3번 로그인 → 매번 독립적으로 유효한 완전 인증 ADMIN 세션 발급 확인(세션 ID
  전부 다름, `isAuthenticated:true`). 상세는 `findings/documenso-2fa-backup-code-replay/`
  (description.md, evidence/reproduction.md, cwe-analysis.md). **아직 벤더 미신고, 외부 공개 금지.**
  전제조건: 공격자가 이미 피해자의 비밀번호 + 유출된 백업 코드 1개를 알고 있어야 함 — "1회성이어야
  할 유출 사고가 영구 백도어가 되는" 결함.
- 참고: SAST 과정에서 서브에이전트가 **리포지토리/환경 안에 삽입된 가짜 system-reminder(프롬프트
  인젝션 시도)를 발견하고 무시**했다고 보고함 — 출처 미확인, 별도 확인 필요.

---

## 팀 워크플로우로 이관됨

### MediaCMS

| 항목 | 내용 |
|---|---|
| **소프트웨어** | [MediaCMS](https://github.com/mediacms-io/mediacms) |
| **상태** | 🟢 확인됨(팀 `research` 저장소 등록 완료, PR #24 / Campaign [#25](https://github.com/CJ-AI-SecurityWave/research/issues/25) / Finding [#26](https://github.com/CJ-AI-SecurityWave/research/issues/26)) — 교차검수 대기, 벤더 미신고 |
| **스타 수** | ~5,100 |
| **언어/스택** | Python (Django) + React, AGPL-3.0 |
| **선정일** | 2026-09-13 |
| **선정 사유** | 업로드/미디어 처리 기능이 많아 공격 표면이 넓음(Path Traversal, 파일 처리 RCE 후보). 기존 GHSA 1건(RCE, High)만 있어 상대적으로 덜 감사된 상태. 보안 신고 절차 명확 (단, legal safe harbor 문구는 없음 — scope.md 참고) |
| **로컬 재현 환경** | `docker-compose.yaml` / `docker-compose-dev.yaml` / `docker-compose.full.yaml` 제공 확인됨 |

#### 우선순위 검토 영역

- 미디어 업로드/트랜스코딩 파이프라인 (파일 처리 RCE, 기존 GHSA-x3p4-4442-q2c3와 동일 클래스 잔여 버그 가능성)
- 파일 경로/스토리지 처리 (Path Traversal)
- 인증/권한 (공개/비공개 미디어 접근 제어, IDOR)
- API 엔드포인트 인가 일관성
- 서드파티 라이브러리(ffmpeg 등 외부 프로세스 호출) 인젝션 가능성

#### 진행 상황

- [x] 코드베이스 구조 파악 (Phase 1)
- [x] SAST — 발견 후보 목록화 (Phase 2, `analysis/source-code-audit/mediacms-findings.md`) — HIGH 1건, MEDIUM 2건, LOW 1건
- [x] 후보 압축 — HIGH 1건(`media_auth` IDOR)을 Phase 3 최우선 대상으로 선정
- [x] DAST — 로컬 재현 (Phase 3) — **HIGH 발견 재현 성공, FACT로 승격** (`findings/mediacms-media-auth-idor/`)
- [ ] 리포팅 & 벤더 신고 (Phase 4) — 미착수, 사용자 승인 필요

#### 확정된 발견 (FACT)

- **`media_auth` IDOR — 비공개 미디어 전 자산 타입 무단 열람 (CWE-639/863, CVSS 3.1 7.5 High)**:
  로컬 Docker에서 완전 재현. `X_ACCEL_PROTECTED_PATHS`의 세 경로(original/encoded/hls) 전부 +
  자막 + 사용자 업로드 썸네일까지, MediaCMS가 보호하는 **모든 미디어 에셋 타입**이 percent-encoding
  변형(원본/인코딩/HLS) 또는 단순 decoy(자막/썸네일) 방식으로 우회됨을 확인 — 기능 전체의 근본 결함.
  실질 악용은 "대상 미디어의 정확한 uid 또는 파일 경로를 사전에 알아야" 하며(예: 접근 권한이 있었던
  사람이 URL을 알고 있다가 권한 회수 후에도 재접근), 상세는 `findings/mediacms-media-auth-idor/`
  (description.md, poc/, evidence/, cwe-analysis.md). **아직 벤더 미신고, CVE ID 미부여, 외부 공개 금지.**

---

## 완료됨 (취약점 미발견)

### Formbricks

| 항목 | 내용 |
|---|---|
| **소프트웨어** | [Formbricks](https://github.com/formbricks/formbricks) |
| **상태** | ⛔ REJECTED — SAST 완료, 유의미한 취약점 미발견 |
| **선정일** | 2026-09-08 / **종료일** | 2026-09-13 |
| **분석 커밋** | `cd1c6a3d79d6d3dca9ee97e44f2e62f44f8dc474` |
| **조사 범위** | 인증/세션/JWT, Webhook/SSRF, 조직/팀 IDOR, 파일 업로드/Path Traversal, SpiceDB 인가 엔진(coordinator/evaluator/schema.zed) — 5개 영역 병렬 SAST |
| **결론** | 전 영역에서 유의미한 발견 없음. 코드 곳곳에 과거 내부 티켓(ENG-XXXX) 참조 주석과 함께 정확히 이 공격 클래스들을 겨냥한 방어 코드가 이미 존재 — 사전 위협모델링을 거친 것으로 추정되는 방어적 코드베이스. LOW 신뢰도 메모 1건(`contact-survey-link.ts` JWT key reuse, 현재 비exploitable)만 남음 |
| **상세 기록** | `analysis/source-code-audit/formbricks-findings.md` |
| **재검토 트리거** | webhook delivery 내부 로직(SSRF 외), survey response ingestion, feedback-directory/dataset ingestion 파이프라인은 미검토 상태로 남음. 이후 여유 있을 때 재검토 가능 |

---

## 검토했던 다른 후보 (미선정)

목요일 회의에서 비교 검토했던 후보들입니다. Formbricks에서 성과가 없을 경우 대체 후보로 재검토 가능합니다.

| 소프트웨어 | 스타 | 언어 | 기존 GHSA | 비고 |
|---|---|---|---|---|
| Zammad | ~5,900 | Ruby/Vue/TS | 30건 | 이미 많이 감사됨, Rails 경험자 있으면 도전 가능 |
| MediaCMS | ~5,100 | Python | - | 업로드 기능多, 보안 정책 명확 |
| Baserow | ~5,800 | Python | - | 노코드 DB 툴 |
| Checkmk | ~2,400 | Python/C++ | - | 인프라 접근 권한 큼 |
| Documenso | ~14,900 | TypeScript | - | 전자서명 서비스 |
| Miniflux / FreshRSS | ~9,700 / ~15,900 | Go / PHP | - | 코드 규모 작은 편 |

*(참고 사례로 살펴본 CVE: CVE-2026-25991 (Tandoor Recipes, Blind SSRF), CVE-2026-30862 (Appsmith, Stored XSS→관리자 탈취) — 둘 다 우리 대상 선정에 참고)*

---

## 대상 선정 기준 (재확인용)

1. **필수 조건**: 스타 1,000개 이상 / 최근 6개월~1년 내 활동 / 소스 공개 / 로컬 구동 가능 / 보안 신고 절차 존재
2. **우선순위**: 위험 기능 보유 여부(URL fetch, 업로드, 권한 분리, 커스텀 인증) > 유지보수 활발도 대비 코드 규모 > 기존 CVE 이력(너무 적어도, 너무 많아도 판단 필요)

---

## 상태 범례

- 🟡 PENDING: 아직 선택되지 않음
- 🟠 SELECTED: 선택됨, scope.md 업데이트 필요
- 🟢 IN PROGRESS: 분석 중
- ✅ COMPLETED: 분석 완료, PoC & 리포트 생성
- ⛔ REJECTED: 벤더 정책상 불가, 또는 포기
