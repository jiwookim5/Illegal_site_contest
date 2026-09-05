# Claude Code — 신규 CVE 찾기 프로젝트 지시사항

이 파일은 이 프로젝트에만 적용되는 추가 지시사항입니다.
기본 하네스 규칙은 AGENTS.md를 따릅니다.

## 충돌 시 우선순위

이 파일의 지시사항 > AGENTS.md > 전역 CLAUDE.md

안전성이 충돌하면 항상 더 제한적인 것을 따릅니다.

---

## 이 프로젝트의 특성

1. **법적 신중함 필수**: CFAA(미국), 부정 접근죄(한국) 등 현지법 준수
2. **증거의 엄격함**: "발견 가능성" vs "실제 취약점"을 명확히 구분
3. **윤리 우선**: 보상보다 책임 공개와 커뮤니티 보안 기여 우선
4. **타임라인 민감**: 벤더별 Disclosure 시한을 엄격하게 지킬 것

---

## 작업 흐름

### Preflight (매 세션마다)

- targets.md에서 현재 분석 대상 확인
- scope.md의 승인 상태 확인
- 벤더의 Disclosure 정책 재확인 (변경 가능성)
- 이전 CVE와의 중복 확인 (이미 리포트되지 않았나?)

### Phase 1: 분석 대상 선정

- README.md → targets.md로 이동
- 각 후보에 대해:
  - 소스 코드 가용성 확인
  - 보안 이력 조사 (이전 CVE, 보안 권고)
  - 벤더 Disclosure 정책 확인
  - scope.md 업데이트 후 GO 승인 요청

### Phase 2: 소스 코드 리뷰 (SAST)

- analysis/ 폴더에서 진행
- 문제 발견 → "발견 후보"로 기록 (아직 FACT 아님)
- 공통 취약 패턴 검색:
  - SQL Injection (ORM bypass, stored procedure 미사용 등)
  - XSS (template engine 설정, escape 누락)
  - Authentication/Authorization (우회 로직)
  - SSRF, Path Traversal, Insecure Deserialization
  - 암호화 오류, 하드코딩된 secret
  - 종속성 취약점 (npm audit, pip-audit 등)

### Phase 3: 로컬 재현 (DAST)

- Docker에서 대상 소프트웨어 실행
- 발견한 취약점을 실제로 트리거
- PoC 작성 (curl, Python script 등)
- stdout/stderr, 요청/응답 전부 기록
- **재현 불가능** → "발견 후보" 제거
- **재현 성공** → FACT로 기록, findings/에 구조화

### Phase 4: 리포팅 & 공개

- findings/[CVE-XXXX-XXXXX]/ 구성:
  - description.md: What, Why, How
  - poc/: 재현 가능한 스크립트 + 단계
  - evidence/: 요청/응답, 스크린샷
  - cwe-analysis.md: CWE 분류 + CVSS 계산
- 벤더에 비공개 리포트 전송
- Disclosure Timeline 준수
- 공개 시 CVE ID 확보 (mitre.org 또는 벤더)

---

## 금지 행동 (강조)

```
❌ 공개 프로덕션 환경에 무단 테스트
❌ 다른 사용자 데이터 접근/수정/삭제
❌ 웹셸, backdoor, persistence 설치
❌ API 키, DB 계정 등 실제 credential 도용
❌ 벤더 승인 없이 취약점 공개
❌ 소스 코드 무단 배포 (분석 리포트는 OK)
❌ 다른 보안 연구자의 미공개 취약점 선점
```

이 중 하나라도 하려고 하면, AI는 **즉시 거절**해야 합니다.

---

## 한국어 응답

- 한국어로 답변하되, 기술 용어/CVE/CWE/CVSS 등은 영어 유지
- 법적 표현은 명확히 (예: "CFAA 위반 가능성", "한국 부정접근죄 해당")

---

## 성공 기준

- ✅ 로컬 환경에서 취약점 재현 완료
- ✅ PoC 작성 완료
- ✅ CWE 분류 및 CVSS 계산 완료
- ✅ 벤더에 비공개 리포트 전송 완료
- ✅ Disclosure Timeline 준수
- ✅ (선택) CVE ID 부여 및 공개

---

## 참고

- OWASP Top 10: https://owasp.org/www-project-top-ten/
- CWE 목록: https://cwe.mitre.org/data/downloads/
- CVSS 3.1: https://www.first.org/cvss/v3.1/specification-document
- Responsible Disclosure Best Practices: https://www.eff.org/deeplinks/2021/09/why-coordinated-vulnerability-disclosure-matters
