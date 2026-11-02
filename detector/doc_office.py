"""오피스 문서(DOCX·PPTX·XLSX, 옛 형식 DOC·XLS·PPT)에서 글자와 숨긴 글자를 꺼낸다."""
import io
import re
import zipfile
from xml.etree import ElementTree

from doc_common import MAX_BYTES, hex_rgb, hide_reasons, merge_runs


# ---------------------------------------------------------------- 오피스 문서 (docx·pptx·xlsx)
#
# 모두 zip 안의 XML 이다. 글자 모양은 문서에 직접 적힌 값만 본다 (스타일 상속은 따지지 않는다).

def _local(tag):
    return tag.rsplit("}", 1)[-1]


def _attr(el, name):
    """이름공간과 무관하게 속성값을 읽는다 (w:val, val 모두)."""
    for k, v in el.attrib.items():
        if _local(k) == name:
            return v
    return None


def _xml(z, name):
    try:
        return ElementTree.fromstring(z.read(name))
    except (KeyError, ElementTree.ParseError):
        return None


def _docx_run_hide(rpr):
    if rpr is None:
        return ()
    rgb, size, vanish = None, None, False
    for el in rpr:
        tag = _local(el.tag)
        if tag in ("vanish", "specVanish") and (_attr(el, "val") or "true").lower() not in ("0", "false", "off"):
            vanish = True
        elif tag == "color":
            if (_attr(el, "themeColor") or "").lower() in ("background1", "bg1"):
                rgb = (1.0, 1.0, 1.0)
            else:
                rgb = hex_rgb(_attr(el, "val"))
        elif tag == "sz":
            try:
                size = int(_attr(el, "val")) / 2          # 반 포인트 단위
            except (TypeError, ValueError):
                pass
    out = hide_reasons(rgb, size)
    if vanish:
        out.insert(0, "숨김 속성(Word 숨긴 텍스트)")
    return tuple(out)


def docx_paragraphs(data):
    out, runs = [], []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        # 본문·머리말·꼬리말·각주·미주. 머리말처럼 잘 안 보는 곳에 넣는 경우도 있다
        parts = ["word/document.xml"] + sorted(
            n for n in z.namelist() if re.match(r"word/(header|footer)\d*\.xml$|word/(foot|end)notes\.xml$", n))
        for name in parts:
            root = _xml(z, name)
            if root is None:
                continue
            for p in root.iter():
                if _local(p.tag) != "p":
                    continue
                texts = []
                for r in p.iter():
                    if _local(r.tag) != "r":
                        continue
                    rpr = next((c for c in r if _local(c.tag) == "rPr"), None)
                    text = "".join((c.text or "") if _local(c.tag) == "t" else " " if _local(c.tag) == "tab" else ""
                                   for c in r)
                    texts.append(text)
                    runs.append((text, _docx_run_hide(rpr)))
                out.append("".join(texts))
    return out, merge_runs(runs)


def pptx_paragraphs(data):
    out, runs = [], []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        slides = sorted((n for n in z.namelist() if re.match(r"ppt/slides/slide\d+\.xml$", n)),
                        key=lambda n: int(re.sub(r"\D", "", n)))
        for name in slides:
            root = _xml(z, name)
            if root is None:
                continue
            for p in root.iter():
                if _local(p.tag) != "p":
                    continue
                texts = []
                for r in p:
                    if _local(r.tag) not in ("r", "fld"):
                        continue
                    rpr = next((c for c in r if _local(c.tag) == "rPr"), None)
                    text = "".join(c.text or "" for c in r if _local(c.tag) == "t")
                    rgb, size = None, None
                    if rpr is not None:
                        try:
                            size = int(_attr(rpr, "sz")) / 100      # 1/100 pt
                        except (TypeError, ValueError):
                            pass
                        for fill in rpr:
                            if _local(fill.tag) == "solidFill":
                                for c in fill:
                                    if _local(c.tag) == "srgbClr":
                                        rgb = hex_rgb(_attr(c, "val"))
                                    elif _local(c.tag) == "schemeClr" and _attr(c, "val") in ("bg1", "lt1"):
                                        rgb = (1.0, 1.0, 1.0)
                    texts.append(text)
                    runs.append((text, tuple(hide_reasons(rgb, size))))
                out.append("".join(texts))
    return out, merge_runs(runs)


def _xlsx_col(ref):
    """'BC12' -> 55 (1부터)."""
    n = 0
    for ch in re.match(r"[A-Z]*", ref or "").group(0):
        n = n * 26 + ord(ch) - 64
    return n


def _xlsx_styles(z):
    """셀 서식 번호 -> 숨긴 방식. 글꼴(흰색·작은 크기)과 숫자 서식(;;; 처럼 값을 안 보이게)을 본다."""
    root = _xml(z, "xl/styles.xml")
    if root is None:
        return {}
    blank_fmts = set()
    fonts, xfs = [], []
    for el in root:
        tag = _local(el.tag)
        if tag == "numFmts":
            for f in el:
                code = (_attr(f, "formatCode") or "").replace('""', "")
                if code and set(code) <= {";"}:
                    blank_fmts.add(_attr(f, "numFmtId"))
        elif tag == "fonts":
            for f in el:
                rgb, size = None, None
                for c in f:
                    if _local(c.tag) == "color":
                        v = _attr(c, "rgb")
                        if v and len(v) == 8:
                            rgb = hex_rgb(v[2:])               # ARGB
                        elif _attr(c, "theme") == "0":
                            rgb = (1.0, 1.0, 1.0)                  # 테마 0 = 배경(흰색)
                    elif _local(c.tag) == "sz":
                        try:
                            size = float(_attr(c, "val"))
                        except (TypeError, ValueError):
                            pass
                fonts.append(tuple(hide_reasons(rgb, size)))
        elif tag == "cellXfs":
            xfs = [x for x in el if _local(x.tag) == "xf"]
    out = {}
    for i, xf in enumerate(xfs):
        why = list(fonts[int(_attr(xf, "fontId") or 0)]) if fonts else []
        if _attr(xf, "numFmtId") in blank_fmts:
            why.append("값을 안 보이게 하는 서식(;;;)")
        out[str(i)] = tuple(why)
    return out


def xlsx_paragraphs(data):
    """셀 글자와 숨긴 방식(숨긴 시트·행·열, 흰 글꼴·작은 글꼴, ;;; 서식)."""
    out, runs = [], []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        shared = []
        root = _xml(z, "xl/sharedStrings.xml")
        if root is not None:
            shared = ["".join(t.text or "" for t in si.iter() if _local(t.tag) == "t")
                      for si in root if _local(si.tag) == "si"]
        styles = _xlsx_styles(z)
        # 시트 파일 -> 숨긴 시트인가 (workbook.xml 의 state 와 관계 파일의 대상 경로를 잇는다)
        hidden_sheets = set()
        wb, rels = _xml(z, "xl/workbook.xml"), _xml(z, "xl/_rels/workbook.xml.rels")
        if wb is not None and rels is not None:
            target = {_attr(r, "Id"): _attr(r, "Target") for r in rels}
            for sh in wb.iter():
                if _local(sh.tag) == "sheet" and _attr(sh, "state") in ("hidden", "veryHidden"):
                    t = (target.get(_attr(sh, "id")) or "").lstrip("/")
                    hidden_sheets.add(t if t.startswith("xl/") else "xl/" + t)
        sheets = sorted((n for n in z.namelist() if re.match(r"xl/worksheets/sheet\d+\.xml$", n)),
                        key=lambda n: int(re.sub(r"\D", "", n)))
        for name in sheets:
            sheet = _xml(z, name)
            if sheet is None:
                continue
            hidden_cols = set()
            for col in sheet.iter():
                if _local(col.tag) == "col" and _attr(col, "hidden") in ("1", "true"):
                    hidden_cols.update(range(int(_attr(col, "min") or 0), int(_attr(col, "max") or 0) + 1))
            for row in sheet.iter():
                if _local(row.tag) != "row":
                    continue
                row_hidden = _attr(row, "hidden") in ("1", "true")
                for c in row:
                    if _local(c.tag) != "c":
                        continue
                    kind, text = _attr(c, "t"), None
                    if kind == "s":
                        v = next((x.text for x in c if _local(x.tag) == "v"), None)
                        try:
                            text = shared[int(v)]
                        except (TypeError, ValueError, IndexError):
                            text = None
                    elif kind == "inlineStr":
                        text = "".join(t.text or "" for t in c.iter() if _local(t.tag) == "t")
                    elif kind == "str":
                        text = next((x.text for x in c if _local(x.tag) == "v"), None)
                    if not text or not text.strip():
                        continue
                    why = list(styles.get(_attr(c, "s") or "0", ()))
                    if name in hidden_sheets:
                        why.append("숨긴 시트")
                    if row_hidden:
                        why.append("숨긴 행")
                    if _xlsx_col(_attr(c, "r")) in hidden_cols:
                        why.append("숨긴 열")
                    out.append(text)
                    runs += [(text, tuple(why)), ("", ())]
        if not out:                       # 시트를 못 읽었으면 공유 문자열이라도 본다
            out = shared
    return out, merge_runs(runs)


# ---------------------------------------------------------------- 옛 오피스 문서 (doc·xls·ppt)
#
# 형식마다 글자 위치 표(doc 조각 표, xls 공유 문자열, ppt 글자 레코드)를 따로 해석하는 대신,
# 본문 스트림에서 글자열만 뽑는다. 한글은 세 형식 모두 UTF-16 으로 저장되고, 영문만 든 글은 8비트로 저장될 수 있다.
# 광고 문구를 찾는 데는 충분하고 견고하다. 숨김 서식은 구분하지 않는다.

LEGACY_STREAMS = {"DOC": ("WordDocument",), "XLS": ("Workbook", "Book"), "PPT": ("PowerPoint Document",)}
_UTF16_RUN = re.compile("[\uAC00-\uD7A3\u3131-\u318E\u0020-\u007E\u00B7\u0370-\u03FF"
                        "\u0400-\u04FF\u2000-\u206F\u3000-\u303F\uFF01-\uFF5E]{4,}")
_ASCII_RUN = re.compile(rb"[\x20-\x7e]{8,}")
_LETTER = re.compile("[\uAC00-\uD7A3\u3131-\u318EA-Za-z\u0400-\u04FF\uFF21-\uFF5A]")


def legacy_strings(raw):
    """바이너리 스트림 속 글자열. UTF-16 은 짝수·홀수 위치 양쪽에서 찾는다 (글자 시작 위치가 정렬되지 않은 경우)."""
    out, seen = [], set()
    for start in (0, 1):
        text = raw[start:len(raw) - (len(raw) - start) % 2].decode("utf-16-le", "replace")
        for m in _UTF16_RUN.finditer(text):
            run = " ".join(m.group(0).split())
            if len(_LETTER.findall(run)) >= 3 and run not in seen:
                seen.add(run)
                out.append(run)
    for m in _ASCII_RUN.finditer(raw):
        run = " ".join(m.group(0).decode("ascii").split())
        if len(_LETTER.findall(run)) >= 4 and run not in seen:
            seen.add(run)
            out.append(run)
    return out


def legacy_paragraphs(kind):
    def extract(data):
        import olefile
        ole = olefile.OleFileIO(io.BytesIO(data))
        try:
            out = []
            for name in LEGACY_STREAMS[kind]:
                if ole.exists(name):
                    out += legacy_strings(ole.openstream(name).read(MAX_BYTES))
            return out, []
        finally:
            ole.close()
    return extract
