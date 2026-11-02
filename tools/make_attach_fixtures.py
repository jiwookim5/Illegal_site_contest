"""첨부파일 검사 시험용 문서(testsite5/files)를 만든다.

- PDF : Edge 로 HTML 을 인쇄해 만든다 (흰 글씨로 숨긴 광고 포함)
- HWP : 한글 5.0 바이너리 형식(OLE 복합 파일 + 압축 본문)을 직접 쓴다
- HWPX: 한글 OWPML(zip + XML) 형식을 직접 쓴다

한 번 만들어 저장소에 넣어 두므로 평소에는 다시 돌릴 필요가 없다.
    .venv\\Scripts\\python tools\\make_attach_fixtures.py
    .venv\\Scripts\\python tools\\make_attach_fixtures.py hidden   문서 안 숨긴 글자 시험 파일만
    .venv\\Scripts\\python tools\\make_attach_fixtures.py office   오피스 문서·zip 시험 파일만
"""
import os
import struct
import sys
import zipfile
import zlib

from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "testsite5", "files")

AD_1 = "카지노 첫충 30% 지급 텔레그램 @promo_777"
AD_2 = "먹튀검증 안전놀이터 가입쿠폰 바로가기 www.safe-toto.cc"
AD_3 = "라이브카지노 에볼루션 무료머니 지급 문의 텔레그램"


# ---------------------------------------------------------------- PDF

def make_pdfs():
    docs = {
        "notice.pdf": "<h1>2026년 민원 처리 안내</h1><p>민원 접수는 평일 09시부터 18시까지 "
                      "1층 민원실에서 가능합니다.</p><p>문의: 민원봉사과</p>",
        "apply.pdf": "<h1>참가 신청서</h1><p>성명, 연락처를 적어 제출해 주십시오.</p>"
                     f"<p style='color:#fff;font-size:2px'>{AD_1}</p>"
                     "<p>제출처: 총무과</p>",
    }
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page()
        for name, body in docs.items():
            page.set_content("<html><head><meta charset='utf-8'><style>"
                             "body{font-family:'Malgun Gothic'}</style></head>"
                             f"<body>{body}</body></html>")
            page.pdf(path=os.path.join(OUT, name))
        browser.close()


# ---------------------------------------------------------------- HWP (한글 5.0)

SECTOR = 512
ENDOFCHAIN, FREESECT, FATSECT, NOSTREAM = 0xFFFFFFFE, 0xFFFFFFFF, 0xFFFFFFFD, 0xFFFFFFFF


def _pad(data, size):
    """미니 스트림을 쓰지 않도록 모든 스트림을 4096 바이트 이상, 섹터 배수로 맞춘다."""
    size = max(size, len(data), 4096)
    size = -(-size // SECTOR) * SECTOR
    return data + b"\x00" * (size - len(data))


def _dir_entry(name, kind, child=NOSTREAM, right=NOSTREAM, start=ENDOFCHAIN, size=0):
    raw = name.encode("utf-16-le") + b"\x00\x00"
    return (raw.ljust(64, b"\x00") + struct.pack("<HBB", len(raw), kind, 1)
            + struct.pack("<III", NOSTREAM, right, child) + b"\x00" * 16
            + struct.pack("<I", 0) + b"\x00" * 16 + struct.pack("<IQ", start, size))


def write_ole(path, streams):
    """streams: {"FileHeader": bytes, "BodyText/Section0": bytes, ...}

    형제 항목은 정렬된 오른쪽 사슬로 잇는다. 균형 트리는 아니지만 읽기에는 충분하다.
    """
    blobs, start, fat = {}, 0, []
    for name, data in streams.items():
        data = _pad(data, 0)
        n = len(data) // SECTOR
        blobs[name] = (start, len(data), data)
        fat += [start + i + 1 for i in range(n - 1)] + [ENDOFCHAIN]
        start += n

    storages = sorted({n.split("/")[0] for n in streams if "/" in n})
    top = sorted([n for n in streams if "/" not in n] + storages,
                 key=lambda s: (len(s), s.upper()))
    entries = ["Root Entry"] + top
    for st in storages:
        entries += sorted((n for n in streams if n.startswith(st + "/")),
                          key=lambda s: (len(s), s.upper()))
    index = {n: i for i, n in enumerate(entries)}

    def chain(names):
        return {a: index[b] for a, b in zip(names, names[1:])}

    right = chain(top)
    for st in storages:
        right.update(chain(sorted((n for n in streams if n.startswith(st + "/")),
                                  key=lambda s: (len(s), s.upper()))))

    dir_bytes = b""
    for n in entries:
        if n == "Root Entry":
            dir_bytes += _dir_entry(n, 5, child=index[top[0]])
        elif n in storages:
            kids = sorted((k for k in streams if k.startswith(n + "/")),
                          key=lambda s: (len(s), s.upper()))
            dir_bytes += _dir_entry(n, 1, child=index[kids[0]], right=right.get(n, NOSTREAM))
        else:
            s, size, _ = blobs[n]
            dir_bytes += _dir_entry(n.split("/")[-1], 2, right=right.get(n, NOSTREAM),
                                    start=s, size=size)
    dir_bytes = dir_bytes.ljust(-(-len(dir_bytes) // SECTOR) * SECTOR, b"\x00")
    dir_start, dir_n = start, len(dir_bytes) // SECTOR
    fat += [dir_start + i + 1 for i in range(dir_n - 1)] + [ENDOFCHAIN]
    start += dir_n

    fat_n = 1
    while (len(fat) + fat_n) > fat_n * (SECTOR // 4):
        fat_n += 1
    fat_start = start
    fat += [FATSECT] * fat_n
    fat += [FREESECT] * (fat_n * (SECTOR // 4) - len(fat))

    difat = [fat_start + i for i in range(fat_n)] + [FREESECT] * (109 - fat_n)
    header = (b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1" + b"\x00" * 16
              + struct.pack("<HHHHH", 0x3E, 3, 0xFFFE, 9, 6) + b"\x00" * 6
              + struct.pack("<IIIIIIIII", 0, fat_n, dir_start, 0, 4096,
                            ENDOFCHAIN, 0, ENDOFCHAIN, 0)
              + struct.pack("<109I", *difat))

    with open(path, "wb") as fp:
        fp.write(header)
        for name in streams:
            fp.write(blobs[name][2])
        fp.write(dir_bytes)
        fp.write(struct.pack(f"<{len(fat)}I", *fat))


def _record(tag, body):
    return struct.pack("<I", tag | (len(body) << 20)) + body


def _para_text(text, with_tab=False):
    units = text.encode("utf-16-le")
    if with_tab:     # 인라인 제어 문자(탭, 8칸)를 앞에 붙여 건너뛰기를 시험한다
        units = struct.pack("<8H", 9, 0, 0, 0, 0, 0, 0, 9) + units
    return units + struct.pack("<H", 13)


def make_hwp(path, paragraphs):
    body = b""
    for i, text in enumerate(paragraphs):
        body += _record(0x10 + 50, b"\x00" * 22)                 # PARA_HEADER (내용 생략)
        body += _record(0x10 + 51, _para_text(text, with_tab=(i == 1)))
    header = b"HWP Document File".ljust(32, b"\x00") + struct.pack("<II", 0x05000300, 1)
    comp = zlib.compressobj(9, zlib.DEFLATED, -15)
    section = comp.compress(body) + comp.flush()
    preview = "\n".join(paragraphs[:1]).encode("utf-16-le")
    write_ole(path, {
        "FileHeader": header.ljust(256, b"\x00"),
        "BodyText/Section0": section,
        "PrvText": preview,
    })


# ---------------------------------------------------------------- HWPX

def make_hwpx(path, paragraphs):
    ns = ('xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
          'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"')
    paras = "".join(f'<hp:p><hp:run><hp:t>{t}</hp:t></hp:run></hp:p>' for t in paragraphs)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/hwp+zip")
        z.writestr("Contents/section0.xml",
                   f'<?xml version="1.0" encoding="UTF-8"?><hs:sec {ns}>{paras}</hs:sec>')


# ---------------------------------------------------------------- 문서 안에서 숨긴 글자

AD_4 = "슬롯머신 무료체험 가입머니 즉시지급 텔레그램 @slot_777"
AD_5 = "비아그라 시알리스 정품 최저가 카톡 viag88"
AD_6 = "토토사이트 안전놀이터 추천 첫충 20% 문의"


def make_hwp_styled(path, shapes, paragraphs):
    """글자 모양을 넣은 HWP. shapes: [(크기 pt, 글자색 0xBBGGRR)], paragraphs: [[(글, 모양 번호), ...]]"""
    def char_shape(size_pt, color):
        body = bytearray(72)
        struct.pack_into("<i", body, 42, int(size_pt * 100))
        struct.pack_into("<I", body, 52, color)
        return bytes(body)

    docinfo = b"".join(_record(0x10 + 5, char_shape(*sh)) for sh in shapes)
    body = b""
    for runs in paragraphs:
        text = "".join(t for t, _ in runs)
        body += _record(0x10 + 50, b"\x00" * 22)                # PARA_HEADER
        body += _record(0x10 + 51, _para_text(text))            # PARA_TEXT
        table, pos = b"", 0
        for t, sid in runs:                                     # PARA_CHAR_SHAPE: (시작 위치, 모양 번호)
            table += struct.pack("<II", pos, sid)
            pos += len(t.encode("utf-16-le")) // 2
        body += _record(0x10 + 52, table)

    def deflate(data):
        comp = zlib.compressobj(9, zlib.DEFLATED, -15)
        return comp.compress(data) + comp.flush()

    header = b"HWP Document File".ljust(32, b"\x00") + struct.pack("<II", 0x05000300, 1)
    write_ole(path, {
        "FileHeader": header.ljust(256, b"\x00"),
        "DocInfo": deflate(docinfo),
        "BodyText/Section0": deflate(body),
    })


def make_hwpx_styled(path, char_prs, paragraphs):
    """글자 모양을 넣은 HWPX. char_prs: [(크기 pt, '#RRGGBB')], paragraphs: [[(글, 모양 번호), ...]]"""
    hh = 'xmlns:hh="http://www.hancom.co.kr/hwpml/2011/head"'
    ns = ('xmlns:hs="http://www.hancom.co.kr/hwpml/2011/section" '
          'xmlns:hp="http://www.hancom.co.kr/hwpml/2011/paragraph"')
    props = "".join(f'<hh:charPr id="{i}" height="{int(pt * 100)}" textColor="{c}"/>'
                    for i, (pt, c) in enumerate(char_prs))
    paras = "".join("<hp:p>" + "".join(f'<hp:run charPrIDRef="{sid}"><hp:t>{t}</hp:t></hp:run>'
                                       for t, sid in runs) + "</hp:p>" for runs in paragraphs)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), "application/hwp+zip")
        z.writestr("Contents/header.xml", f'<?xml version="1.0" encoding="UTF-8"?><hh:head {hh}>'
                                          f'<hh:charProperties>{props}</hh:charProperties></hh:head>')
        z.writestr("Contents/section0.xml",
                   f'<?xml version="1.0" encoding="UTF-8"?><hs:sec {ns}>{paras}</hs:sec>')


def make_hidden():
    """문서 안에서 흰 글씨·아주 작은 글자로 숨긴 광고 (testsite5 view?id=4)."""
    make_hwpx_styled(os.path.join(OUT, "hide_white.hwpx"), [(10, "#000000"), (10, "#FFFFFF")],
                     [[("2027년 주민 참여 예산 설명회 자료", 0)], [("설명회는 구청 대강당에서 열립니다.", 0)],
                      [(AD_4, 1)]])
    make_hwp_styled(os.path.join(OUT, "hide_tiny.hwp"), [(10, 0x000000), (1, 0x000000)],
                    [[("설명회 참석자 명단", 0)],
                     [("일시: 11월 둘째 주 화요일 ", 0), (AD_5, 1), (" 장소: 대강당", 0)]])
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page()
        # 인쇄할 때 Edge 는 흰 글씨를 회색으로 바꿔 칠한다. 한글·워드로 만든 문서처럼 흰색 그대로 넣는다
        page.set_content("<html><head><meta charset='utf-8'><style>body{font-family:'Malgun Gothic';"
                         "print-color-adjust:exact;-webkit-print-color-adjust:exact}</style>"
                         "</head><body><h1>설명회 질의응답</h1><p>질의응답 내용을 정리했습니다.</p>"
                         f"<p style='color:#fff'>{AD_6}</p><p>문의: 기획예산과</p>"
                         f"<p style='font-size:1px'>{AD_4}</p></body></html>")
        page.pdf(path=os.path.join(OUT, "hide.pdf"))
        browser.close()


# ---------------------------------------------------------------- 오피스 문서·zip 묶음

AD_7 = "오피스타 출장안마 24시 후불 카톡 op777"
AD_8 = "바카라 에볼루션 첫충 20% 텔레그램 @bac_88"
AD_9 = "급전대출 무직자 당일 승인 카톡 loan99"
W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'
A = ('xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
     'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"')
X = 'xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"'


def _zip(path, files):
    """날짜를 고정해 다시 만들어도 같은 파일이 되게 한다."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, body in files.items():
            z.writestr(zipfile.ZipInfo(name, date_time=(2026, 10, 3, 0, 0, 0)), body)


def _docx(path, paragraphs):
    """paragraphs: [[(글, rPr XML), ...]]"""
    body = "".join("<w:p>" + "".join(f"<w:r><w:rPr>{rpr}</w:rPr><w:t xml:space=\"preserve\">{t}</w:t></w:r>"
                                     for t, rpr in runs) + "</w:p>" for runs in paragraphs)
    _zip(path, {"[Content_Types].xml": "<Types/>",
                "word/document.xml": f'<?xml version="1.0" encoding="UTF-8"?><w:document {W}><w:body>{body}'
                                     f'</w:body></w:document>'})


def make_office():
    """오피스 문서·zip 묶음 시험 파일 (testsite5 view?id=5)."""
    _docx(os.path.join(OUT, "event.docx"),
          [[("주민 참여 예산 우수 사례 공모 안내", "<w:b/>")],
           [("자세한 내용은 붙임을 참고하십시오. ", ""), (AD_7, "<w:vanish/>")]])
    _docx(os.path.join(OUT, "clean.docx"),
          [[("우수 사례 심사 기준", "<w:b/>")], [("주민 참여도, 효과성, 지속 가능성을 봅니다.", "")]])
    slide = (f'<?xml version="1.0" encoding="UTF-8"?><p:sld {A}><p:cSld><p:spTree>'
             '<p:sp><p:txBody><a:p><a:r><a:rPr sz="2800"/><a:t>설명회 발표 자료</a:t></a:r></a:p>'
             f'<a:p><a:r><a:rPr sz="100"/><a:t>{AD_8}</a:t></a:r></a:p></p:txBody></p:sp>'
             '</p:spTree></p:cSld></p:sld>')
    _zip(os.path.join(OUT, "slides.pptx"), {"[Content_Types].xml": "<Types/>",
                                            "ppt/presentation.xml": f"<p:presentation {A}/>",
                                            "ppt/slides/slide1.xml": slide})
    strings = "".join(f"<si><t>{t}</t></si>" for t in ("사업명", "예산(천원)", "마을 도서관 개선", AD_9))
    _zip(os.path.join(OUT, "budget.xlsx"), {"[Content_Types].xml": "<Types/>",
                                            "xl/workbook.xml": f"<workbook {X}/>",
                                            "xl/sharedStrings.xml": f"<sst {X}>{strings}</sst>"})
    _zip(os.path.join(OUT, "bundle.zip"),
         {"붙임1_결과보고.hwpx": open(os.path.join(OUT, "report.hwpx"), "rb").read(),
          "붙임2_신청서.hwp": open(os.path.join(OUT, "form.hwp"), "rb").read()})


def main():
    if sys.argv[1:] == ["hidden"]:       # 숨긴 글자 시험 파일만 새로 만든다
        make_hidden()
        print("OK hidden")
        return
    if sys.argv[1:] == ["office"]:       # 오피스 문서·zip 시험 파일만 새로 만든다 (Edge 불필요)
        make_office()
        print("OK office")
        return
    os.makedirs(OUT, exist_ok=True)
    make_pdfs()
    make_hwp(os.path.join(OUT, "plan.hwp"),
             ["2026년 구민 체육대회 계획", "일시: 10월 셋째 주 토요일",
              AD_2, "장소: 구민체육센터"])
    make_hwp(os.path.join(OUT, "form.hwp"),
             ["민원 신청서 서식", "성명", "주소", "연락처"])
    make_hwpx(os.path.join(OUT, "report.hwpx"),
              ["행사 결과 보고", "참가 인원 320명", AD_3])
    print("OK", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
