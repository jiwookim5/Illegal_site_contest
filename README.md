# 신규 CVE 찾기 — 취약점 발견 & 분석 프로젝트

## 개요

- **목표**: 최신 오픈소스/상용 소프트웨어에서 **미공개(0-day) 또는 새롭게 발견된 CVE** 찾기
- **방식**: 공개된 소스 코드 분석, 보안 패턴 검토, 알려진 취약점 패턴 적용
- **산출**: CVE 리포트, PoC, 근거 (CWE), 영향도 분석
- **윤리**: 책임 있는 공개(Responsible Disclosure) 원칙 준수

## 프로젝트 구조

```
cve-hunting/
├── README.md           (이 파일)
├── AGENTS.md           (AI 하네스 계약서 — 보안 분석용)
├── scope.md            (대상 소프트웨어 범위 및 제약)
├── CLAUDE.md           (프로젝트별 지시사항)
├── targets.md          (분석 대상 목록)
├── analysis/
│   ├── source-code-audit/  (소스 코드 리뷰 결과)
│   ├── dependency-check/   (의존성 분석, SCA)
│   └── pattern-matching/   (알려진 취약 패턴 검색)
├── findings/
│   ├── [CVE-XXXX-XXXXX]/
│   │   ├── description.md
│   │   ├── poc/
│   │   ├── evidence/
│   │   └── cwe-analysis.md
├── research/
│   ├── vulnerability-patterns.md (공부한 패턴 정리)
│   └── tools.md         (사용한 도구/스크립트)
└── retrospective/      (분석 결과 검증, 배운 점)
```

## 작업 방식

### Phase 1: Target 선정
- 분석할 오픈소스/소프트웨어 선택
- 버전, 소스코드 가용성, 보안 이력 검토
- scope.md에 기록

### Phase 2: 정적 분석 (SAST)
- 소스 코드 직접 리뷰
- 보안 패턴 검색 (SQL Injection, XSS, SSRF, 인증/인가 우회 등)
- 의존성 취약점 (npm audit, OWASP Dependency-Check 등)

### Phase 3: 동적 분석 (DAST, 선택)
- 로컬 환경에서 대상 소프트웨어 실행
- PoC 작성 및 재현성 검증
- **중요**: 실제 공개 인스턴스는 테스트하지 않음 (대상이 오픈소스인 경우만)

### Phase 4: 리포팅
- CVE 기술서 작성 (Description, Root Cause, CVSS, CWE)
- PoC 포함
- 벤더에 책임 있는 공개 (Disclosure Timeline)

---

## 하네스 구조

이 프로젝트는 AGENTS.md의 일반 규칙을 따르되, 몇 가지 특수성이 있습니다:

- **AI Draft와 증거 분리**: 소스 코드 리뷰는 "발견 후보"이지 "확정 취약점"이 아님
- **재현성 검증**: 발견한 취약점을 로컬에서 실제로 재현할 때만 FACT로 기록
- **책임 공개**: 벤더 연락처, 응답 기한, 공개 예정일 등을 scope에 기록

---

## 윤리 원칙

1. **무단 테스트 금지**: 본인이 통제할 수 있는 환경(로컬 Docker 등)에서만
2. **책임 공개**: 벤더가 패치할 시간 제공 후 공개
3. **선의의 목적**: 보상/명성 추구는 보조, 보안 커뮤니티 기여가 1순위
4. **법 준수**: 각국 법률(CFAA 등)에서 "보안 연구" 범위 준수

---

## 시작하기

1. `targets.md`에서 분석할 소프트웨어 선택 (또는 추가)
2. `scope.md` 읽고 제약 확인
3. analysis/ 폴더에서 소스 코드 리뷰 시작
4. 취약점 발견 → findings/ 폴더에 기록
5. 벤더에 책임 공개 → 공개 가능 시 공개

---

**상태**: 초기화 완료, 대상 선정 대기 중
