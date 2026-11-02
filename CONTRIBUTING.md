# 함께 작업하는 방법

## 꼭 지킬 것

- **실제 공공기관 누리집은 점검하지 않습니다.** 시험은 로컬 시험 사이트(`시험사이트 실행.bat`, `tools/serve.py`, `testsite/scenario_suite.py`)에서만 합니다.
- `main`에 바로 push하지 않습니다. 브랜치를 따서 작업하고 PR로 합칩니다.
- 실행 파일(`.exe`), 빌드 결과(`build/`, `dist/`), 점검 결과(`out/`, `result*.json`, `evidence/`), 압축 파일은 커밋하지 않습니다. `.gitignore`에 들어 있습니다.

## 작업 순서

```powershell
git switch main
git pull
git switch -c 작업-이름          # 예: fix/jamo-false-positive, feat/hwpx-hidden
# ... 수정 ...
git add <파일>
git commit -m "무엇을 왜 바꿨는지 한 줄로"
git push -u origin 작업-이름
```

GitHub에서 PR을 열고, 다른 팀원 1명이 확인한 뒤 합칩니다.

## PR 올리기 전에 확인할 것

탐지 로직(`detector/`)이나 판정 사전(`lexicon.py`)을 바꿨다면 회귀 점검을 돌려 기존 시험 사이트 결과가 나빠지지 않았는지 확인합니다.

```powershell
# 처음 한 번: main에서 기준 결과 만들기 (_regress/baseline.json, 커밋되지 않음)
.venv\Scripts\python tools\regress.py --save-baseline

# 작업 브랜치에서: 기준과 비교
.venv\Scripts\python tools\regress.py
```

PR 설명에 회귀 점검 결과(점수 변화, 새로 생긴 오탐·미탐)를 적어 주세요.

저장·조치·CSV·UI를 바꾼 경우 아래 검사도 실행합니다. UI 검사는 headless Edge와 임의 포트의 localhost 시험 서버만 사용합니다.

```powershell
.venv\Scripts\python tools\test_persistence.py
.venv\Scripts\python tools\test_ui_history.py
.venv\Scripts\python tools\test_request_safety.py
.venv\Scripts\python tools\test_scan_ui_controls.py
.venv\Scripts\python tools\test_ui_result_regressions.py
.venv\Scripts\python tools\test_keywords_ui.py
.venv\Scripts\python tools\test_scan_issue_fixes.py
.venv\Scripts\python tools\test_scan_exclusions.py
.venv\Scripts\python tools\test_resume_exclusions.py
```

검색 보조 탐색을 바꾼 경우 `tools/test_search_*.py`의 8개 검사도 실행합니다. 검색 API는 모의 응답을 사용하며, 대상 URL 재검사는 localhost 시험 서버에서만 확인합니다. `test_scan_exclusions.py`는 Google 검색 결과 재검사·제출 연계에서도 제외 주소를 열지 않는지 함께 검사합니다.

회귀시험 원본은 `_regress/runs/<실행 ID>/`에 누적 보존됩니다. `baseline.json`은 비교 기준이고 `last.json`은 최근 요약입니다.
`regress.py`는 점수 미달, 검출 변화, 허용되지 않은 요청, 실행 오류가 있으면 종료 코드 1을 반환합니다.
문맥 판정·탐색을 바꾼 경우 `.venv\Scripts\python tools\test_detection_regressions.py`와 `.venv\Scripts\python tools\lexicon_real.py`도 실행합니다.
판정 점수·문맥 규칙을 바꾸면 `tools\test_scoring_boundaries.py`(띄어쓰기 경계, 피해 상담 글, 검색 유도 도배 글)도, robots.txt 해석·점검 순서·다시 열기·정체 처리·알림창·조치 확인·증거 촬영·첨부 해석·본문 추출 범위를 바꾸면 `tools\test_robots.py`와 `tools\test_real_site_fixes.py`도 실행합니다.
기존 기준에도 있는 미탐은 수정으로 생긴 회귀와 구분해 보고하십시오. OCR을 건너뛴 경우 OCR 검증을 완료했다고 쓰지 않습니다.

`test_scan_issue_fixes.py`는 증거 촬영 후 스타일 복원, 숨긴 iframe과 정상 대조, 판정 사전, 조회/처리 URL 구분, 선택자 안정성, 21페이지 반복 타이머를 실제 localhost·Edge에서 검사합니다. 선택자 보강으로 회귀 기준의 문자열이 달라졌다면, 기준 파일을 덮어쓰기 전에 기존/새 선택자가 같은 DOM 요소와 탐지 유형을 가리키는지 확인합니다.

기본 의존성을 바꿀 때는 `requirements.in`과 `uv pip compile requirements.in --generate-hashes -o requirements.lock` 결과를 함께 검토합니다.
`runs/`, `review.sqlite3`와 SQLite 임시 파일은 실행 기록이므로 커밋하지 않습니다.

탐지 성능을 고쳤다면 우회 기법 시험 사이트도 돌립니다. 새로 잡힌 항목이 있으면 `--sync`로 정답 파일의 상태를 고쳐 함께 커밋합니다 ([설명](testsite_evasion/README.md)).

```powershell
.venv\Scripts\python tools\evasion_check.py
```

## 새 시험 사이트 이름

`testsite`~`testsite16`은 회귀 점검 기준이라 그대로 둡니다. 새 시험 사이트는 번호 대신 주제를 붙여 `testsite_<주제>`로 만듭니다(예: `testsite_evasion`). 포트는 `시험사이트 실행.bat`에서 쓰지 않은 번호를 고릅니다.

## 커밋 메시지

이 저장소는 커밋 메시지를 한국어로, 바뀐 동작이 드러나게 씁니다.

- 좋은 예: `탐지 사전: 외화 환전 안내를 도박 '환전'으로 잡지 않기`
- 나쁜 예: `fix`, `수정`

## 실행 파일 배포

제출하거나 공유할 실행 파일은 `tools\build.ps1`로 빌드한 뒤 GitHub **Releases**에 올립니다.
태그는 날짜로 붙입니다(예: `v2026.10.10`).

우회 보정을 바꾼 경우 `.venv\Scripts\python tools\test_evasion_regressions.py`로 타이머 상한, 닫힌 Shadow DOM, 투명 효과의 정상 대조, 문장 집계와 CSS 표시 순서도 확인합니다.

## 글꼴·canvas·느린 응답 보정 회귀

관련 탐지 동작을 바꾼 경우 `.venv\Scripts\python tools\test_remaining_evasion.py`도 실행합니다. 실제 로컬 HTTP·Edge를 사용해 큰 음수 bottom과 일반 하단 본문, 같은 도메인의 숨김 광고 문맥, 독립 글꼴 치환, 최종 canvas 픽셀, 17초 응답을 확인합니다. 글꼴 시험은 정답 파일이나 glyph 이름을 런타임에 신뢰하지 않습니다.

`fonttools[woff]`를 변경하면 의존성 잠금과 EXE의 `fontTools`·`brotli` 포함 여부도 확인합니다. 글꼴 윤곽 복원·canvas 그리기 관찰 결과를 일반 이미지 OCR의 성공으로 기록하지 않습니다. URL별 결과는 모집요강 12쪽 규칙으로 비교합니다. 내용이 같아도 쿼리·경로가 다른 URL의 검출을 기준 통과 목적으로 지우지 않습니다. 기존 우회 정답의 기준 충돌 2건은 원문과 실제 응답 대조 후 필수 정답으로 정정했습니다(`testsite_evasion/README.md`의 URL 정답 기준 정정 참조).
