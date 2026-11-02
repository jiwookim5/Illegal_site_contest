# 기획서(서식4) 다시 만들기

제출본: `docs/기획서_훤히.docx` (A4, 10쪽 — 요강 한도 10매). 그림은 `docs/기획서_그림/`.

| 파일 | 역할 |
|---|---|
| `make_doc.js` | 기획서 .docx 생성 (본문 내용이 이 파일 안에 있음) |
| `도식.html` | 그림 1(시스템 구조)·그림 2(사용자 흐름) 원본 |
| `render_figs.py` | `도식.html` 을 Edge 로 찍어 PNG 로 저장 (Pillow 필요) |
| `capture_screens.py` | 그림 3~5: 실행 중인 화면(포트 8911)을 1.5배로 찍어 구간을 잘라 붙임 |

```powershell
# 그림 1·2 다시 찍기 (.venv 필요)
.venv\Scripts\python docs\기획서_원본\render_figs.py docs\기획서_원본\도식.html docs\기획서_그림

# 기획서 생성 (Node.js 와 docx 패키지 필요: npm install docx@9)
node docs\기획서_원본\make_doc.js docs\기획서_그림 docs\기획서_훤히.docx
```

화면 캡처(그림 3~5)는 10/20 화면(주소 입력 → 점검 → 결과 확인 → 조치·기록 4단계)으로 찍었습니다.
훤히를 `--no-browser --port 8911 --out <임시 폴더>` 로 따로 띄우고, testsite4 **사본**을 8768 포트로 띄워 씁니다
(`$env:SITE = "<사본 절대 경로>"; .venv\Scripts\python tools\serve.py 8768`).

1. 점검 설정에서 증거 사진·화면 저장을 켜고 `http://127.0.0.1:8768/www/main` 을 점검
2. 사본 `css/p4.css` 의 `.ico::before` 광고 문구를 지우고 [조치 확인]
3. `capture_screens.py <작업 폴더> docs\기획서_그림` 실행 — 그림 3(요약·조치 확인 결과 + 목록 앞부분),
   그림 4(4번 광고의 조치·기록 화면: 판정 등급·조치 확인 + 증거 사진), 그림 5(검색엔진 추가 탐색 화면,
   대상 도메인은 예시 `www.example.go.kr` 로 바꿔 찍으며 검색은 하지 않음)

잘라 붙인 곳에는 점선을 넣고 그림 설명에 '(중간 생략)'을 적습니다. 상태 표시줄의 실행 기록 경로(사용자 폴더명)는 숨겨 찍습니다.
쪽 수가 10쪽을 넘지 않는지 Word 에서 확인합니다(그림 크기는 `make_doc.js` 의 `img(..., 너비)`).
신청자명·연락처는 제출 전에 Word 에서 직접 채웁니다.
