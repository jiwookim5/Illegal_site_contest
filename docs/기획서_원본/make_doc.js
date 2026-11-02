// 서식4 기획서(.docx) 생성. 사용: node make_doc.js <그림 폴더> <출력 파일>
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell,
  AlignmentType, WidthType, ShadingType, BorderStyle, LevelFormat, PageNumber,
  Footer, HeadingLevel, VerticalAlign, PageBreak,
} = require("docx");

const [figDir, outFile] = process.argv.slice(2);
const FONT = "맑은 고딕";
const RED = "D7141E", DARK = "171717", MUTED = "5F5F5F", HEAD_BG = "F0F0F0";
const CONTENT_W = 9638;             // A4 폭 11906 - 좌우 여백 2cm(1134)×2

// ── 글자 조각: "**굵게**" 와 "`코드`" 만 지원 ──
function runs(text, opt = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|`[^`]+`)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...opt }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), bold: true, ...opt }));
    else out.push(new TextRun({ text: t.slice(1, -1), font: "Consolas", size: (opt.size || 20) - 2, ...opt,
                                 ...(opt.font ? {} : { font: "Consolas" }) }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...opt }));
  return out;
}
const P = (text, o = {}) => new Paragraph({ children: runs(text, o.run), spacing: { after: 100, line: 300 },
                                            alignment: o.align || AlignmentType.JUSTIFIED, ...o.para });
const H1 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_1, children: [new TextRun(t)],
                                  spacing: { before: 240, after: 140 } });
const H2 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_2, children: [new TextRun(t)],
                                  spacing: { before: 220, after: 120 },
                                  border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: RED, space: 2 } } });
const H3 = (t) => new Paragraph({ heading: HeadingLevel.HEADING_3, children: [new TextRun(t)],
                                  spacing: { before: 180, after: 80 } });
const B = (text, level = 0) => new Paragraph({ children: runs(text), numbering: { reference: "bul", level },
                                               spacing: { after: 60, line: 290 } });
const N = (text) => new Paragraph({ children: runs(text), numbering: { reference: "num", level: 0 },
                                    spacing: { after: 60, line: 290 } });
const SRC = (text) => new Paragraph({ children: runs(text, { size: 16, color: MUTED }), spacing: { after: 120 } });

function img(file, widthPx, caption) {
  const buf = fs.readFileSync(path.join(figDir, file));
  const w = buf.readUInt32BE(16), h = buf.readUInt32BE(20);      // PNG IHDR
  const height = Math.round(widthPx * h / w);
  return [
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 40 }, keepNext: true,
      children: [new ImageRun({ type: "png", data: buf, transformation: { width: widthPx, height },
                                altText: { title: caption, description: caption, name: file } })] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 160 },
      children: [new TextRun({ text: caption, size: 17, color: MUTED })] }),
  ];
}

const border = { style: BorderStyle.SINGLE, size: 4, color: "BFBFBF" };
const borders = { top: border, bottom: border, left: border, right: border };
function table(widths, rows, { head = true, firstColHead = false } = {}) {
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA }, columnWidths: widths,
    rows: rows.map((cells, r) => new TableRow({
      tableHeader: head && r === 0,
      children: cells.map((c, i) => {
        const isHead = (head && r === 0) || (firstColHead && i === 0);
        return new TableCell({
          borders, width: { size: widths[i], type: WidthType.DXA }, verticalAlign: VerticalAlign.CENTER,
          shading: isHead ? { fill: HEAD_BG, type: ShadingType.CLEAR, color: "auto" } : undefined,
          margins: { top: 60, bottom: 60, left: 100, right: 100 },
          children: String(c).split("\n").map((line) => new Paragraph({
            alignment: isHead && r === 0 ? AlignmentType.CENTER : AlignmentType.LEFT,
            spacing: { after: 0, line: 270 },
            children: runs(line, { size: 18, bold: isHead || undefined }) })),
        });
      }),
    })),
  });
}
const gap = () => new Paragraph({ spacing: { after: 60 }, children: [] });

// ───────────────────────────── 본문 ─────────────────────────────
const body = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 },
    children: [new TextRun({ text: "『 공공 웹사이트 불법광고 탐지 도구 개발 공모전 』", size: 24, color: MUTED })] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 280 },
    children: [new TextRun({ text: "기 획 서", size: 44, bold: true })] }),

  H1("1. 참가자 정보"),
  table([2200, 7438], [
    ["신청자명", ""],
    ["연락처", "(핸드폰)                                   (이메일)"],
    ["작품명", "훤히 — 공공 누리집 숨은 불법광고 탐지 도구"],
  ], { head: false, firstColHead: true }),

  H1("2. 개발 기획 내용"),

  // ── 1) 배경 및 목적 ──
  H2("1) 개발 제안 배경 및 목적"),
  H3("문제 인식: 공공 도메인의 신뢰도를 빌리는 불법광고"),
  P("2025년 10월 말 기준 언론 조사에서 `go.kr` 도메인 **61개 누리집에서 불법광고 1,169건**이 확인되었다. 보건복지부 345건, 나주시 320건, 인천시 103건, 우체국 쇼핑몰 68건 등 중앙부처와 지방자치단체, 공공 서비스를 가리지 않았고, 보건복지부 누리집에서는 마약 거래 광고까지 발견되었다. 해당 기관은 \"사실을 인지하지 못했다\"고 답했다."),
  P("수법의 핵심은 **서버를 뚫지 않는다**는 점이다. 불법광고 업자는 기관 누리집 검색창에 광고 문구를 반복 입력해 만든 검색결과 주소를 구글 등 검색엔진이 수집하도록 유도한다. 검색엔진은 신뢰도가 높은 공공기관 페이지를 상단에 배치하므로, 도박 키워드를 검색한 사람에게 기관 도메인이 광고 문구를 제목으로 달고 노출된다. 게시판에 글을 올리는 경우에도 글자색을 배경과 같게 하거나 화면 밖으로 밀어내는 등 **사람 눈에는 보이지 않고 검색엔진에는 보이도록** 숨긴다."),
  SRC("출처: 매일경제, 「불법 광고 놀이터 된 공공기관 웹사이트」, 2025.11.16."),

  H3("현행 체계의 공백"),
  B("**발견 수단이 없다.** 광고가 서버에 저장되지 않거나 화면에 보이지 않아, 담당자가 게시판을 살펴봐도 찾을 수 없다. 기존 게시판 금칙어 필터는 자모 분해(ㅋㅏㅈㅣㄴㅗ)나 닮은꼴 글자(ｃａｓｉｎｏ) 치환에 쉽게 우회된다."),
  B("**관리 주체와 규모 파악이 어렵다.** 검색엔진에 노출된 광고는 각 누리집 담당자가 직접 검색엔진에 조치를 요청해야 하고, 정부도 불법·상업 광고의 규모와 형태를 파악하지 못하고 있다. 행정안전부는 전 부처에 점검·조치 요청 공문을 보내고 있으나 이를 수행할 도구가 없다."),
  B("**과업 범위 밖이다.** 누리집 운영·유지관리 용역에는 변조 방지 모니터링과 웹 취약점 진단은 있어도 은닉형 불법광고 점검은 과업 항목이 아니다."),
  SRC("출처: SBS Biz, 「공공기관 검색했는데 꿀알바?…정부 홈페이지 관리 '사각지대'」, 2026.1.22."),

  H3("개발 목적"),
  P("담당자가 누리집 주소 하나만 넣으면 하위 페이지·게시글·댓글·iframe·첨부파일까지 훑어 **숨겨진 불법광고를 찾아 유형과 위치를 알려주고**, 검색엔진을 통한 광고 노출 경로(검색창 악용)까지 **예방과 사후 확인** 양쪽에서 점검하는 도구를 만든다. 결과는 조치 방법·증거 화면과 함께 제공해 담당자가 바로 조치하고 기록할 수 있게 한다."),

  // ── 2) 상세 설명 ──
  H2("2) 개발 상세 설명"),
  H3("설계 원리"),
  P("불법광고는 \"사람에게는 숨기고 검색엔진에는 보이게\" 만드는 것이 목적이다. 이 모순이 곧 탐지 지점이다. 훤히는 세 가지 어긋남을 측정한다."),
  table([3200, 3200, 3238], [
    ["비교", "어긋나는 경우", "탐지 유형"],
    ["문서에 있는 글자 ↔ 화면에 보이는 글자", "투명·배경색 글씨, 화면 밖·크기 0·잘린 영역", "투명 텍스트, 화면 밖 은닉"],
    ["쓰여진 글자 ↔ 의미하는 단어", "ｃａｓｉｎｏ, ㅋㅏㅈㅣㄴㅗ", "닮은꼴 글자 위장, 자모 분해"],
    ["본문 글자 ↔ 검색엔진이 읽는 곳", "메타 태그·속성값·첨부파일·검색결과 주소", "추가 유형"],
  ]),
  ...img("그림1_시스템구조.png", 560, "[그림 1] 훤히 시스템 구조와 처리 흐름"),

  H3("주요 탐지 유형 4종 (result.json)"),
  table([2000, 7638], [
    ["유형", "판정 근거"],
    ["닮은꼴 글자 위장\nHOMOGLYPH", "전각·키릴·그리스·수학용 문자 등 호환 분해(NFKC) 시 라틴 글자로 되돌아가는 문자, 요강 정의대로 글자 자리에 넣은 숫자·라틴 글자(`cas1n0`, `카ㅈl노`)가 섞인 경우"],
    ["자모 분해\nJAMO", "호환 자모·조합용 자모를 다시 합쳤을 때 음절이 새로 만들어지는 경우. 여러 요소에 나누어 쓴 자모(`<span>ㅋㅏ</span><span>ㅈㅣ</span>…`)는 문단으로 합쳐 판정"],
    ["투명 텍스트\nTRANSPARENT", "`opacity`·`filter:opacity()` 0 근접, `color:transparent`·`-webkit-text-fill-color`, 알파 합성 후 배경과의 대비비 1.2 미만"],
    ["화면 밖 은닉\nOFFSCREEN", "`display:none`·`visibility:hidden`, 글자 크기 1px 이하(`transform` 축소 반영), 문서 밖 좌표, `text-indent`, `clip`·`clip-path`로 잘린 넓이 0, 상위 요소 `overflow:hidden` 밖으로 밀린 글자"],
  ]),
  P("가상 요소(`::before`·`::after`)로 넣은 글자, Shadow DOM 내부, 여러 겹 중첩된 iframe까지 대상에 포함한다. 위치는 요강 표기 규칙에 맞춰 **하나의 요소만 가리키는지 검증한 CSS 선택자**로 보고하며, 태그 이름만으로 된 선택자(`span`)는 쓰지 않아 채점 시 댓글이 추가로 불러와지더라도 여러 요소를 가리키지 않게 한다.", { para: { spacing: { before: 100, after: 100, line: 300 } } }),

  H3("추가 탐지 유형 (result_extra.json)"),
  P("아래 유형은 화면에서 점검 설정의 **추가 광고 유형 검사**(기본 꺼짐, 꺼 두면 주요 4종만 검사)나 해당 추가 검사를 켰을 때 함께 검사되며, 터미널 실행은 기본으로 모두 검사한다.", { para: { spacing: { after: 80, line: 290 } } }),
  table([2600, 7038], [
    ["유형", "내용"],
    ["레이어 은폐 OCCLUDED", "다른 요소에 완전히 덮여 보이지 않는 광고"],
    ["메타·속성·링크", "`title`·`description` 메타 태그, `alt`·`aria-label` 속성값, 화면에 드러나지 않는 외부 도박·성인 사이트 링크"],
    ["첨부파일 ATTACHMENT_AD", "첨부 PDF·한글(HWP·HWPX)·MS 오피스(옛 형식 포함)·그림·zip 안 문서의 광고와 문서 안에서 숨긴 방식(흰 글씨·작은 글자·숨긴 텍스트·숨긴 시트). 확장자 없는 주소·자바스크립트 내려받기 단추도 처리, 파일은 열거나 실행하지 않음"],
    ["그림 속 광고 IMAGE_TEXT_AD", "광고 문구를 배너·포스터 그림으로 만들어 올린 경우. Windows 내장 글자 인식(한국어 OCR)으로 읽어 같은 사전으로 판정하며 외부 전송·GPU가 필요 없음. 첨부한 그림 파일과 글자층 없는 스캔 PDF는 '그림 속 글자 검사' 설정과 관계없이 첨부파일 검사에서 같은 방식으로 읽음 (선택 기능)"],
    ["글꼴 치환·canvas\nFONT_TEXT_AD·CANVAS_TEXT_AD", "웹 글꼴의 글자 모양을 바꾸어 문서 글자와 화면 글자를 다르게 만든 광고(동봉 한글 글꼴 윤곽과 정확히 맞을 때만 복원), 문서 글자 없이 canvas에 그린 광고(그리기 기록과 최종 픽셀이 일치할 때만)"],
    ["크롤러 위장 CLOAKING", "같은 주소를 검색엔진 크롤러 신원으로 다시 조회해, 크롤러에게만 광고를 보여주는 응답 탐지"],
    ["검색창 반사 SEARCH_REFLECT", "검색결과 반사형 광고에 악용될 수 있는 검색창 (예방 점검, 등급: 취약·주의)"],
    ["검색엔진 색인 SEARCH_INDEXED", "검색엔진에 이미 색인되어 광고가 노출 중인 주소 (사후 확인, 등급: 피해 발생 또는 광고 확인됨·주의)"],
    ["게시판 노출 광고 VISIBLE_AD", "게시판·방명록·댓글에 숨기지 않고 올린 광고 글 (실제 사례에서 가장 흔한 유형)"],
    ["연계 사이트 변질 LINK_HIJACKED", "패밀리 사이트·옛 행사 누리집 링크의 도메인이 만료되어 도박·성인 광고로 바뀐 경우(피해 발생 또는 광고 확인됨)와 도메인 판매·없음(주의). 외부 도메인마다 첫 화면 글자만 한 번 받고, 공공 도메인은 조회하지 않음 (선택 기능)"],
    ["검색 노출 광고\nSEARCH_INDEXED_AD 등 4종", "구글 검색 결과에 기관 도메인이 광고 제목·요약으로 노출된 주소. 노출 그 자체(SEARCH_INDEXED_AD), 주소에 광고 문구가 포함된 검색결과 반사형(SEARCH_PARAMETER_AD), 원본 글은 삭제되었으나(404·410) 검색에 남은 경우(SEARCH_REMOVED_AD), 현재 페이지에도 광고가 있는 경우(SEARCH_LIVE_AD)로 나눈다. 뒤의 두 가지는 상세 설정의 '수집한 주소에 접속해 지금도 광고가 있는지 확인'을 켜 해당 페이지에 접속할 때만 가려낸다 (선택 기능, 검색 API 사용)"],
  ]),

  H3("핵심 차별점 ① 검색결과 반사형 광고 대응"),
  P("실제 피해의 주된 수법인 검색창 악용은 광고가 **주소와 검색엔진 색인에만** 존재하므로, 누리집 안에서 숨은 글자를 찾는 방식으로는 원리상 닿을 수 없다. 훤히는 이를 예방과 두 가지 사후 확인으로 다룬다."),
  B("**예방 — 검색창 점검(외부 의존 없음, 폐쇄망 동작):** 탐색 중 발견한 GET 검색 폼마다 광고가 아닌 **무해한 표식 문자열로 한 번** 조회한다. 표식이 페이지 제목·본문에 그대로 나타나는지, `noindex`(메타 태그·X-Robots-Tag 헤더)·`canonical`·`robots.txt` 설정 여부를 확인하여 **취약**(제목 반사·색인 차단 없음)과 **주의**로 등급을 매긴다. `robots.txt` 차단은 검색엔진이 페이지를 읽는 것만 막을 뿐 외부 링크로 알려진 주소의 색인은 막지 못하므로 '주의'로 분류하고 `noindex` 적용을 안내한다."),
  B("**사후 — 색인 목록 점검:** 담당자가 Google Search Console에서 내려받은 색인 페이지 목록(CSV)을 넣으면 주소마다 한 번 조회하여, 주소에 담긴 광고 문구가 지금도 제목·본문에 나타나는 경우 **피해 발생 또는 광고 확인됨**으로 보고하고 색인 삭제 요청과 `noindex` 적용을 안내한다. 목록에서 처음 알게 된 숨은 검색 경로는 예방 점검으로 넘겨 반사 여부를 확인한다. 기관이 자체 누리집 권한으로 받는 파일이므로 **검색 API 키나 비용이 들지 않는다.**"),
  B("**사후 — 검색 노출 확인(선택, 검색 API 사용):** Search Console 권한이 없거나 지금 국민에게 보이는 검색 결과를 바로 확인할 때 쓴다. 결과 화면의 [추가 탐색하기]를 통해 실제 노출 사례에서 뽑은 **광고 유형별 고정 검색 단어**(7개 분류 25개, 직접 추가 가능)로 `site:기관도메인 단어`를 구글에 검색하고, 제목·요약을 본 점검과 **동일한 사전**으로 판정한다(단어가 들어갔다는 것만으로는 보고하지 않음). 검색 전에 최대 호출 수를 보여 주며, 결과는 `result_extra.json`에 합쳐지고 점검 보고서와 같은 양식의 검색 보고서로 남는다. 키는 소스와 분리된 `search.env`(환경변수 `SERPAPI_API_KEY`)에 두며, 키가 없어도 본 점검은 그대로 동작한다."),

  H3("핵심 차별점 ② 공공 누리집 구조에 맞춘 탐색"),
  P("공공 누리집 게시판(전자정부 표준프레임워크 등)은 글 목록을 `javascript:fn_view('1024')`, 행 클릭(`onclick`), 스크립트 클릭 이벤트, 숨은 폼 페이지 번호로 연결해 일반 링크만 따라가면 게시글에 닿지 못한다. 훤히는 코드에서 이동 주소를 읽고, 읽을 수 없으면 요소를 눌러 **목적지 주소만 확보**한다(이동은 브라우저 안에서 취소, GET이 아닌 요청 차단, 삭제·수정·로그아웃 등은 누르지 않음). 비동기·'더보기' 댓글과 스크립트가 늦게 끼워 넣는 광고(iframe 안 포함)도 기다려 검사한다. 대기 시간은 페이지 로딩 완료 시점을 기준으로 하며 같은 메뉴는 한 번만 실행하여 **500페이지를 약 1분 30초에** 점검한다."),
  P("점검 범위는 입력한 누리집으로 한정하되, `www` 유무가 다른 주소와 진입 주소가 넘겨 준 주소(리다이렉트)는 같은 누리집으로 본다. 게시판·민원을 `bbs.기관.go.kr`, `기관.go.kr:8080`처럼 별도 주소로 운영하는 기관을 위해 **'서브도메인도 점검' 옵션**으로 같은 기관 도메인까지 넓힐 수 있다. 같은 서버에 함께 올라간 다른 기관 누리집(가상 호스트)은 점검 권한 밖이므로 옵션을 켜도 따라가지 않는다."),

  H3("오탐 억제: \"감춰졌는가\"와 \"광고인가\"를 분리"),
  P("숨김 처리 자체는 위반이 아니다. 본문 바로가기 링크나 스크린리더용 안내문도 화면에서 감춰진다. 훤히는 은닉 여부와 별개로 광고 여부를 판정하며, 광고에서만 쓰는 확정 표현(먹튀·안전놀이터·첫충 등)은 단독으로, 카지노·토토나 성매매 업소 이름처럼 보도·도서 소개에도 나오는 종목 이름은 다른 단서가 하나 더 있을 때, 마약·대포통장·대포폰·불법 대출·불법 고수익 알바처럼 **예방 안내에도 쓰이는 표현은 판매·연락처·금액 같은 유인 신호가 함께 있을 때만** 광고로 본다. 신고·처벌·예방·주의 같은 안내 문구가 있으면 점수를 낮춰 \"대포통장 매입 제의를 받으면 신고하세요\" 같은 공고를 광고로 보지 않는다. 부모만 숨겨지고 자식은 보이는 요소처럼 **실제로 보이는 글**도 보고하지 않는다."),
  P("판정 결과는 판정 근거의 수준에 따라 **확실·의심·경계** 등급으로 나누고, 어떤 키워드와 숨김 방식이 검출되었는지 함께 보여 주어 담당자가 확실한 것부터 조치하게 한다. 판정 사전은 담당자가 **점검 키워드** 화면에서 직접 보완한다. 분류(확정 표현·종목·업종 이름·거래 표현·약한 말·안내문 표현)마다 판정 방식을 설명해 두고, 단어를 더하기 전에 **시험해 보기**로 같은 문장이 숨겨진 글일 때와 화면에 보이는 글일 때 각각 어떻게 판정되는지, 어떤 표현이 걸렸는지 확인하게 해 오탐을 유발하는 단어 추가를 막는다. 새 은어가 나타나도 프로그램을 다시 받지 않고 다음 점검부터 반영된다."),

  H3("활용 데이터 및 주요 기술"),
  table([2200, 7438], [
    ["구분", "내용"],
    ["활용 데이터", "점검 대상 누리집의 공개 페이지(HTML·CSS·스크립트 실행 결과), 게시글 첨부파일(PDF·한글·MS 오피스 문서·그림·zip)\n자체 구축 불법광고 판정 사전(도박·성인물 확정 표현, 마약·대포통장·돈세탁·불법 대출·불법 알바 표현과 은어, 연락처·주소·금액 유인 신호, 예방·신고 안내 문구, 담당자가 화면에서 추가·보완)\n유니코드 문자 데이터(호환 분해 NFKC, 한글 자모 블록)\n(선택) 기관이 Google Search Console에서 내려받은 색인 페이지 목록\n(선택) SerpApi로 받은 구글 검색 결과(제목·요약·주소)"],
    ["렌더링·탐색", "Python, Playwright로 Windows 기본 탑재 Microsoft Edge 구동, 브라우저 안에서 계산된 스타일·글자 범위 측정, Navigation API로 자바스크립트 이동 가로채기"],
    ["문자 처리", "NFKC 정규화, 자모 재결합, 제로폭·구분 문자 제거, 숫자 치환(t0t0→toto) 복원"],
    ["파일 처리", "PDF(pypdf, 스캔 페이지는 pypdfium2로 그려 인식), HWP·옛 형식 DOC·XLS·PPT(OLE 레코드 직접 해석), HWPX·DOCX·PPTX·XLSX(zip+XML) 글자와 글자 모양 추출, 그림 글자는 Windows 내장 OCR(Windows.Media.Ocr)"],
    ["배포", "설치 없는 Windows 11 실행 파일(PyInstaller), 결과 화면은 로컬 웹 서버 + Edge 앱 창"],
  ]),
  P("**AI 적용 여부:** 적격평가는 위치와 유형의 정확한 일치로 채점되고, 규칙으로 판정 가능한 영역에 생성형 모델을 쓰면 검출 시간과 운영 비용만 늘어난다. 따라서 **상용 AI API를 사용하지 않으며** 본 점검에는 외부 호출·토큰 비용·망 제약이 없다. 외부 API는 선택 기능인 검색 노출 확인의 검색결과 API(SerpApi, AI 아님) 하나뿐이며, 검색 1회가 호출 1건이고 실행 전에 최대 호출 수를 보여 준다. 신종 은어처럼 사전이 놓칠 수 있는 경계 사례는 향후 CPU만으로 동작하는 경량 판정 모델을 보조로 붙여 보완할 수 있다.", { para: { spacing: { before: 120, after: 100, line: 300 } } }),

  H3("탐지 결과 확인·안내·관리 기능과 화면 구성"),
  ...img("그림2_사용자흐름.png", 610, "[그림 2] 담당자 사용 흐름"),
  table([2000, 7638], [
    ["화면", "기능"],
    ["주소 입력·점검", "주소 하나만 넣고 [점검 시작]. 점검 설정은 접혀 있어 바꾸지 않아도 되며, 지난 점검 결과를 목록에서 다시 열거나 지운다. 점검 중에는 진행 막대와 현재 점검 페이지, [점검 중지] 표시"],
    ["결과 확인", "의심 항목·미조치·조치완료·오탐 처리와 지난 점검 대비 새로 생김·사라짐 요약, 처리 상태·판정 등급(확실·의심·경계)·유형·검색어로 거르기. 메뉴·하단·위젯처럼 **여러 페이지에 동일하게 포함된 광고는 한 줄로 묶고** 공통 서식에서 한 번에 지우도록 안내. 일부만 점검된 경우 사유와 점검하지 못한 주소를 표시"],
    ["조치·기록", "항목마다 유형 설명·페이지·판정 이유·판정 등급과 걸린 키워드, 처리 상태와 담당자 메모, 단계별 조치 방법, **숨김을 풀어 찍은 증거 사진**, 복원한 글자·위치(복사), 점검 때 저장한 누리집 화면과 원본 코드. [이전 광고]·[다음 광고]로 차례로 처리"],
    ["조치 확인", "관리자 화면에서 광고를 지운 뒤 누르면 광고가 나온 페이지만 다시 열어 동일한 기준으로 판정하며, 사라졌거나 글이 삭제되었으면 **자동으로 조치완료**, 남아 있으면 '아직 있음'으로 표시 — 조치완료는 담당자 입력이 아니라 도구가 확인한 사실"],
    ["점검 키워드", "판정 표현을 분류별로 보고 단어 더하기·기본 단어 끄기·기본값 되돌리기, 시험해 보기(숨긴 글·보이는 글 판정과 등급, 걸린 표현), 다음 점검부터 화면·터미널 실행 모두에 적용"],
    ["점검 설정", "최대 페이지(기본 5000, 25분을 넘으면 그때까지의 결과로 마침), 천천히 점검(요청 간격·robots.txt), 서브도메인도 점검, 추가 광고 유형 검사, 검출 증거 사진 저장, 방문 페이지 사본 저장, 첨부파일 검사, 검색창 점검, 연계 링크 확인, 그림 속 글자 검사, 크롤러 위장 검사, 색인 목록 — 항목마다 설명, 기본값 그대로 사용 가능"],
    ["추가 탐색", "점검 뒤 결과 화면에서 실행하는 검색 노출 확인: 기본 화면은 도메인·광고 유형·예상 호출 수·시작만, 검색 범위·재검사 등은 접힌 상세 설정, 진행 막대와 질의별 상태, 오류 질의와 사유 표시, 지난 검색 보기, 점검 보고서와 같은 양식의 검색 보고서"],
    ["보고·이력", "결재란이 있는 인쇄용 보고서, 엑셀(CSV), 점검·조치 이력(실행마다 결과·증거 보존), 도움말 창. 창을 새로고침하거나 다시 실행해도 진행하던 단계와 이전 결과로 복원"],
  ]),
  ...img("화면1_탐지결과.png", 440, "[그림 3] 결과 확인 — 광고 하나를 지운 뒤 [조치 확인]: 사라진 광고는 자동 조치완료, 남은 의심 항목과 판정 등급 (중간 생략)"),
  ...img("화면2_증거보기.png", 400, "[그림 4] 조치·기록 — 판정 이유·등급과 걸린 키워드, 조치 확인 결과, 숨김을 풀어 찍은 증거 사진 (중간 생략)"),
  ...img("화면3_검색결과반사.png", 250, "[그림 5] 검색엔진 추가 탐색 — 기본 화면은 도메인·광고 유형·시작만 (대상 도메인은 예시)"),

  H3("검증 결과 (시험 사이트)"),
  table([2300, 5100, 2238], [
    ["시험 대상", "구성", "결과"],
    ["주요 4종 시험 사이트 12종", "정답 101건과 함정 (iframe 중첩, Shadow DOM, 자바스크립트 게시판, 비동기 댓글, 잘림·리다이렉트, 숨겨진 예방 안내문 등)", "101/101 검출, 오탐 0건"],
    ["우회 기법 시험 사이트", "탐지를 피하려는 변형(겹친 투명도·SVG·글자 크기 경계·EUC-KR 등) 정답 145건과 정상 함정 46건", "145/145 검출, 함정 오탐 0/46"],
    ["팀원이 따로 만든 시험 사이트", "모의 포털 4곳 702페이지(정답 70건)와 사례 49개(광고 37·정상 12). 개발과 별도로 만든 정답표로 미탐 10건을 찾아 보완", "70/70, 광고 37/37 검출, 정상 안내글·정상 사례 오판 0건"],
    ["검색결과 반사 시험 사이트", "검색 폼 9종(취약·주의·noindex·함정), 링크 없는 숨은 검색 경로 2종, 색인 목록 CSV", "기대 결과 8건 모두 일치"],
    ["첨부파일 시험 사이트", "PDF·HWP·HWPX·DOCX·PPTX·XLSX·옛 형식 문서·zip, 문서 안 숨긴 글자, 자바스크립트·숨은 폼 내려받기 광고 첨부 17건, 정상 첨부 4건", "17/17 검출, 오탐 0건"],
    ["실제 광고 문구", "검색 결과·보도에서 모은 실제 광고 90건(도박·마약 은어·대포통장·대포유심·성매매 업소 등), 같은 단어가 섞인 정상 문서·보도 제목 86건 (누리집 접속 없음)", "86/90 검출, 오탐 0건"],
    ["검색 노출 확인", "모의 검색 API(광고·정상·결과 없음·오류 응답)로 판정·중지·재시도·병합 시험 / 실제 지자체 누리집 1곳을 고정 단어로 검색(누리집 접속 없음)", "기대대로 / 질의 10회·약 6분, 후보 주소 31개 중 광고 노출 8건(광고 주소 7·검색 노출 1)"],
    ["점검 범위·연계 링크", "같은 주소·`www` 없는 주소·서브도메인·다른 누리집 / 도박·성인으로 바뀐 연계 사이트 3곳, 도메인 판매·없음 2곳, 예방 안내·관광 정상 사이트 2곳", "범위 기대값 일치 / 5/5 일치, 정상 0건, 기능을 끄면 외부 조회 0건"],
    ["게시판 노출 광고", "실제 문구를 옮긴 방명록: 광고 글 6건, 같은 단어가 섞인 정상 글 9건", "6/6 검출, 오탐 0건"],
    ["조치 확인", "광고 지움·그대로·글 삭제(404)·앞에 댓글이 생겨 위치가 밀림·노출 광고 지움·서버 꺼짐", "6가지 모두 기대대로"],
    ["처리 속도", "대규모 시험 사이트 500페이지 (화면 모드 기본 설정, 2회)\n응답마다 0.3초 지연을 넣은 서버 300페이지", "약 1분 31~37초\n약 2분 21초"],
  ]),
  P("시험 사이트는 요강의 채점 규칙(주소·위치·유형 일치, 선택자 유일성)을 재현한 채점기로 평가했으며, 모든 시험에서 시험 서버가 받은 삭제·등록 요청(POST)은 0건이었다.", { para: { spacing: { before: 100, after: 100, line: 300 } } }),

  H3("점검 대상 보호와 배포 형태"),
  B("자체 기관 서버를 대상으로 실행하는 도구이므로 조회(GET)만 하며, 요청 간격 제한·`robots.txt` 준수(천천히 점검)·도구 이름을 밝히는 User-Agent를 갖추었다. 값을 넣는 동작은 검색창 점검의 무해한 표식 조회(검색 기능마다 1회)뿐이고, 연계 링크 확인·조치 확인도 조회만 한다. 오탐이 정상 글 삭제로 이어질 수 있어 누리집의 글을 지우는 기능은 두지 않는다."),
  B("Windows 11에서 설치 없이 실행 파일 하나로 동작한다. Windows 기본 탑재 Edge를 쓰므로 브라우저를 따로 받지 않고, GPU가 필요 없으며 폐쇄망에서도 대상 누리집에 접근 가능하면 동작한다."),

  // ── 3) 활용방안 및 기대효과 ──
  H2("3) 활용방안 및 기대효과"),
  H3("활용 방안"),
  N("**기관 자체 정기 점검:** 누리집 담당자가 설치·계정·비용 없이 월 1회 점검하고, 광고를 지운 뒤 [조치 확인]으로 실제로 사라졌는지 확인해 결재용 보고서로 이력을 남긴다."),
  N("**검색엔진 노출 점검 체계:** 분기마다 Search Console 색인 목록을 넣어 이미 노출된 광고 주소를 찾아 색인 삭제를 요청하고, 취약 검색창에 `noindex`를 적용해 재발을 막는다. 색인 목록 권한이 없거나 보도·민원 직후에는 검색 노출 확인으로 지금 보이는 광고 주소를 바로 확인하고, 글을 지운 뒤에도 남은 주소(삭제 응답)는 검색엔진 삭제 요청 목록으로 쓴다."),
  N("**신종 은어 대응:** 새 광고 은어가 확인되면 담당자가 점검 키워드 화면의 시험해 보기로 정상 공지가 걸리지 않는지 확인한 뒤 바로 더한다. 프로그램을 다시 배포하지 않아도 된다."),
  N("**운영·유지관리 용역 과업 편입:** 과업지시서에 '불법광고 점검'과 결과 CSV 제출을 넣어 정기 점검을 제도화한다."),
  N("**상급기관 취합·품질관리 연계:** 행정안전부의 점검·조치 요청 공문 체계와 연계해 기관별 결과 CSV를 같은 양식으로 취합하고, 공공 웹사이트 품질 진단 항목에 은닉형 불법광고와 검색창 반사 취약을 포함한다."),

  H3("실증 및 운영 계획"),
  table([1800, 3600, 4238], [
    ["단계", "내용", "산출물"],
    ["1단계 시범", "희망 기관 누리집 대상 시범 점검, 미탐·오탐 사례 수집", "사전·판정 기준 보완, 기관별 점검 결과"],
    ["2단계 확산", "중앙부처·지자체 담당자 배포, 사용 안내 교육", "정기 점검 결과 CSV, 조치 이력"],
    ["3단계 제도화", "유지관리 용역 과업·품질관리 진단 항목 반영", "표준 점검 절차, 연도별 현황 통계"],
  ]),
  P("**실증 중 위험 관리·유지보수:** 점검은 조회(GET)만 하고 [점검 중지]로 멈출 수 있으며 결과는 기관 PC에만 저장된다. 새 광고 은어는 점검 키워드 화면에서 더해 재배포 없이 반영하며, 사업 종료 후 기술 지원 체계는 3단계에서 협의한다.", { para: { spacing: { before: 100, after: 100, line: 300 } } }),

  H3("기대효과"),
  P("**정량적 기대효과** — 시험 사이트에서 실제로 잰 값이다.", { para: { spacing: { after: 60, line: 290 } } }),
  table([2000, 3700, 3938], [
    ["지표", "현재 값 (시험 사이트 기준)", "의미"],
    ["점검 시간", "500페이지 약 1분 30초", "은닉 광고를 한 번의 점검으로 목록화"],
    ["검출 정확도", "주요 4종 101/101, 우회 145/145", "숨기는 방식이 바뀌어도 같은 기준"],
    ["오탐", "정상 함정 46건 중 0건", "정상 글 삭제로 이어질 오판 억제"],
    ["도입 비용", "본 점검 비용 0원(설치·계정·API 없음). 검색 노출 확인은 실행 전 최대 호출 수 고지 (25개 단어 전체 선택 시 최대 50회)", "소규모 기관·폐쇄망까지 배포, 이용료는 쓰는 기관이 통제"],
  ]),
  P("**정성적 기대효과**", { para: { spacing: { after: 60, line: 290 } } }),
  table([2000, 7638], [
    ["구분", "내용"],
    ["국민 편익·신뢰 보호", "공공 누리집과 그 검색 결과에서 국민이 도박·성인물 광고에 노출되는 일을 줄이고, 검색창 반사 취약을 막아 공공 도메인의 신뢰도가 광고 홍보에 쓰이는 구조를 끊는다."],
    ["행정 효율", "위치·증거·조치 방법을 함께 제시해 조치 시간을 줄이고, '지웠다'는 보고를 [조치 확인]으로 검증된 사실로 바꾼다. 불법광고 규모를 기관별로 파악한다."],
    ["확산·지속성", "실행 파일 하나로 배포하고 새 광고 은어는 담당자가 직접 더해 유지보수 부담이 작다. 검색 API 이용료는 쓰는 기관만 부담한다."],
    ["혁신성", "숨김·광고 판정의 분리, 공공 게시판 맞춤 탐색, 검색 노출 경로 점검, 첨부·그림 속 광고, 변질된 연계 링크 탐지, 조치 확인을 한 도구로 묶어 기존 필터·점검의 사각지대를 채운다."],
  ]),
  // 표로 끝나면 Word가 끝에 빈 줄을 하나 더 두어 쪽이 넘칠 수 있어, 글자 크기 1pt 의 끝 줄을 직접 둔다
  new Paragraph({ spacing: { before: 0, after: 0, line: 20, lineRule: "exact" }, children: [new TextRun({ text: "", size: 2 })] }),
];

const doc = new Document({
  creator: "훤히",
  title: "공공 웹사이트 불법광고 탐지 도구 개발 공모전 기획서 — 훤히",
  styles: {
    default: { document: { run: { font: FONT, size: 20, color: DARK } } },
    paragraphStyles: [
      { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 28, bold: true, font: FONT, color: DARK }, paragraph: { outlineLevel: 0 } },
      { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 24, bold: true, font: FONT, color: DARK }, paragraph: { outlineLevel: 1 } },
      { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { size: 21, bold: true, font: FONT, color: RED }, paragraph: { outlineLevel: 2 } },
    ],
  },
  numbering: { config: [
    { reference: "bul", levels: [{ level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 400, hanging: 240 } } } }] },
    { reference: "num", levels: [{ level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT,
      style: { paragraph: { indent: { left: 400, hanging: 300 } } } }] },
  ] },
  sections: [{
    properties: { page: { size: { width: 11906, height: 16838 },
                          margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
    footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.CENTER,
      children: [new TextRun({ children: ["- ", PageNumber.CURRENT, " -"], size: 16, color: MUTED })] })] }) },
    children: body,
  }],
});

Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(outFile, buf); console.log("written", outFile, buf.length); });
