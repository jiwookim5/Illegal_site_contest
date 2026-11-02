"""게시글 첨부파일(PDF·HWP·HWPX·DOCX·XLSX·PPTX, zip 묶음) 안에 숨은 광고를 찾는다.

공공 누리집 게시판은 첨부파일을 거의 검사하지 않는다. 본문은 깨끗한데
붙임 문서 속에 광고 문구를 넣어 두면 검색엔진에는 그대로 색인된다.
첨부 링크를 내려받아 글자를 꺼내고, 본문과 같은 사전으로 판정한다.

- 내려받기만 하고 실행하거나 열지 않는다 (글자 추출만)
- 확장자가 아니라 파일 머리(매직 바이트)로 형식을 판별한다
  (전자정부 프레임워크의 FileDown.do 처럼 주소에 확장자가 없는 경우가 흔하다)
"""
import io
import re
import time
import zipfile
from urllib.parse import unquote, urlparse

import ocr
from doc_common import MAX_BYTES, OCR_WAY
from doc_hwp import hwp_paragraphs, hwpx_paragraphs
from doc_office import docx_paragraphs, legacy_paragraphs, pptx_paragraphs, xlsx_paragraphs
from doc_pdf import image_paragraphs, pdf_paragraphs
from judgement import judge_many

ATTACH_EXT = (".pdf", ".hwp", ".hwpx", ".docx", ".xlsx", ".pptx", ".zip", ".doc", ".xls", ".ppt")
# 확장자 없이 내려받기를 처리하는 흔한 주소 모양
DOWNLOAD_HINT = re.compile(r"(filedown|file_down|download|atchfile|fileid|getfile)", re.I)
NAME_IN_TEXT = re.compile(r"[^\s/\\]+\.(pdf|hwpx?|docx?|xlsx?|pptx?|zip|jpe?g|png|gif|bmp)\b", re.I)

SEGMENT_CHARS = 200              # 판정 단위. 길게 묶으면 약한 단어가 쌓여 오탐이 난다
MAX_EVIDENCE = 3                 # 한 파일에서 근거로 보여줄 문단 수
BUDGET_SEC = 180                 # 한 번의 점검에서 첨부파일 내려받기·읽기에 쓰는 시간 상한
FETCH_TIMEOUT_MS = 10000         # 파일 하나를 받는 시간 상한


# ---------------------------------------------------------------- 링크 판별

def looks_like_attachment(href, text=""):
    """주소나 링크 글자로 보아 첨부파일 내려받기 링크인가."""
    path = urlparse(href).path.lower()
    if path.endswith(ATTACH_EXT):
        return True
    if NAME_IN_TEXT.search(text or ""):
        return True
    return bool(DOWNLOAD_HINT.search(href))


def display_name(href, text="", disposition=""):
    """보고서에 적을 파일 이름. 내려받기 헤더 > 링크 글자 > 주소 순으로 찾는다."""
    m = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", disposition or "", re.I)
    if m:
        return unquote(m.group(1)).strip('"')
    m = re.search(r'filename\s*=\s*"?([^";]+)"?', disposition or "", re.I)
    if m:
        name = m.group(1)
        try:                       # 서버가 UTF-8 이름을 latin-1 헤더로 보내는 경우
            name = name.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
        return name
    m = NAME_IN_TEXT.search(text or "")
    if m:
        return m.group(0)
    base = unquote(urlparse(href).path.rsplit("/", 1)[-1])
    return base or href


# ---------------------------------------------------------------- 형식 판별

# OLE 복합 파일은 한글 문서와 옛 오피스 문서(97-2003)가 함께 쓴다. 안의 스트림 이름으로 가린다
OLE_STREAMS = (("FileHeader", "HWP"), ("WordDocument", "DOC"), ("Workbook", "XLS"), ("Book", "XLS"),
               ("PowerPoint Document", "PPT"))


def _ole_kind(data):
    import olefile
    try:
        ole = olefile.OleFileIO(io.BytesIO(data))
    except Exception:
        return None
    try:
        for stream, kind in OLE_STREAMS:
            if ole.exists(stream):
                return kind
        return None
    finally:
        ole.close()


def sniff(data):
    """파일 머리로 형식을 판별한다. 모르는 형식이면 None."""
    if ocr.image_kind(data):
        return "IMAGE"
    if data[:5] == b"%PDF-":
        return "PDF"
    if data[:8] == b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1":
        return _ole_kind(data)
    if data[:2] == b"PK":
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                names = set(z.namelist())
                if "mimetype" in names and "hwp" in z.read("mimetype").decode("ascii", "ignore"):
                    return "HWPX"
                if "word/document.xml" in names:
                    return "DOCX"
                if "xl/workbook.xml" in names:
                    return "XLSX"
                if "ppt/presentation.xml" in names:
                    return "PPTX"
                return "ZIP"
        except Exception:
            return None
    return None


# ---------------------------------------------------------------- zip 묶음

ZIP_MAX_FILES = 30
ZIP_MAX_TOTAL = 50 * 1024 * 1024     # 풀었을 때 합계. 압축 폭탄을 막는다


def zip_paragraphs(data):
    """묶음 안의 문서마다 글자를 꺼낸다. 문단 앞에 [안의 파일 이름] 을 붙인다. 한 겹만 연다."""
    out, hidden, total, opened = [], [], 0, 0
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            if info.is_dir() or opened >= ZIP_MAX_FILES:
                continue
            if info.file_size > MAX_BYTES or total + info.file_size > ZIP_MAX_TOTAL:
                continue
            total += info.file_size
            try:
                inner = z.read(info)
            except Exception:
                continue
            kind = sniff(inner)
            if kind is None or kind == "ZIP":
                continue
            opened += 1
            try:
                paras, hid = EXTRACTORS[kind](inner)
            except Exception:
                continue
            name = _zip_name(info)
            out += [f"[{name}] {p}" for p in paras if p.strip()]
            hidden += hid
    return out, hidden


def _zip_name(info):
    name = info.filename
    if not info.flag_bits & 0x800:          # UTF-8 표시가 없으면 한국어 Windows 압축(CP949)일 수 있다
        try:
            name = name.encode("cp437").decode("cp949")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return name.rsplit("/", 1)[-1]


EXTRACTORS = {"PDF": pdf_paragraphs, "HWP": hwp_paragraphs, "HWPX": hwpx_paragraphs,
              "DOCX": docx_paragraphs, "PPTX": pptx_paragraphs, "XLSX": xlsx_paragraphs,
              "ZIP": zip_paragraphs, "IMAGE": image_paragraphs,
              "DOC": legacy_paragraphs("DOC"), "XLS": legacy_paragraphs("XLS"), "PPT": legacy_paragraphs("PPT")}
KIND_NAMES = {"IMAGE": "그림", "DOC": "DOC(옛 워드)", "XLS": "XLS(옛 엑셀)", "PPT": "PPT(옛 파워포인트)"}


def segments(paragraphs):
    """판정 단위로 자른다. 짧은 문단은 그대로, 긴 문단은 문장 단위로 묶는다."""
    for para in paragraphs:
        para = " ".join(para.split())
        if not para:
            continue
        if len(para) <= SEGMENT_CHARS:
            yield para
            continue
        buf = ""
        for sent in re.split(r"(?<=[.!?。])\s+", para):
            if buf and len(buf) + len(sent) > SEGMENT_CHARS:
                yield buf
                buf = ""
            buf = f"{buf} {sent}".strip()
        if buf:
            yield buf


# ---------------------------------------------------------------- 검사

def _squash(text):
    return re.sub(r"\s+", "", text)


def inspect(data, classify):
    """내려받은 파일 하나를 검사한다.

    (형식, 광고로 판정된 문단 목록, 판정 결과 목록, 숨긴 방식 목록) 을 돌려준다.
    숨긴 방식은 광고 문단과 겹치는 숨긴 글자(흰 글씨·아주 작은 글자 등)의 방식이다.
    형식을 모르면 형식이 None 이고, 형식은 알지만 글을 꺼내지 못하면 문단 목록이 None 이다 ('광고 없음'과 다르다).
    """
    kind = sniff(data)
    if kind is None:
        return None, [], [], []
    try:
        paragraphs, hidden = EXTRACTORS[kind](data)
    except Exception:
        return kind, None, [], []
    hits, verdicts = [], []
    for seg in segments(paragraphs):
        v = classify(seg)
        if v["is_ad"] or v.get("review_candidate"):
            hits.append(seg)
            verdicts.append(v)
    ways = []
    for seg in hits:
        sq = _squash(seg)
        for text, why in hidden:
            t = _squash(text)
            # 숨긴 글자가 광고 문단의 일부(4글자 이상)이거나, 광고 문단이 숨긴 글자 안에 있을 때
            if (len(t) >= 4 and t in sq) or (sq and sq in t):
                ways += [w for w in why if w not in ways]
    return kind, hits, verdicts, ways


class AttachmentScanner:
    """첨부파일을 내려받아 검사한다. 같은 파일은 한 번만 받는다."""

    def __init__(self, request, manners, classify, limit=100, budget_sec=BUDGET_SEC, deadline=None):
        self.request = request      # Playwright APIRequestContext (쿠키·UA 공유)
        self.manners = manners
        self.classify = classify
        self.limit = limit
        # 첨부가 많고 느린 누리집에서 점검 전체가 시간 상한을 넘지 않도록 쓰는 시간을 묶어 둔다
        self.budget_sec = budget_sec
        self.deadline = deadline    # 참을 돌려주면 점검 시간 상한에 닿은 것
        self.spent = 0.0
        self.deferred = set()
        self.on_checkpoint = None
        self.cache = {}             # 파일 주소 -> (이름, 형식, 근거 문단, 판정)
        self.fetched = 0
        self.unread = []            # 받거나 읽지 못한 첨부 {href, reason}. 검출 0건이 '못 봄'인지 가린다

    def _fetch(self, href, text):
        if href in self.cache:
            return self.cache[href]
        if self.fetched >= self.limit or self.spent >= self.budget_sec or (self.deadline and self.deadline()):
            self.deferred.add(href)
            return None
        result = None
        if (self.fetched < self.limit and self.spent < self.budget_sec
                and not (self.deadline and self.deadline()) and self.manners.allowed(href)):
            self.fetched += 1
            self.manners.wait()
            t0 = time.perf_counter()
            why = None
            try:
                resp = self.request.get(href, timeout=FETCH_TIMEOUT_MS, max_redirects=5)
                size = int(resp.headers.get("content-length") or 0)
                if not resp.ok:
                    why = f"응답 {resp.status}"
                elif size > MAX_BYTES:
                    why = "크기 상한 초과"
                else:
                    data = resp.body()
                    if len(data) > MAX_BYTES:
                        why = "크기 상한 초과"
                    else:
                        name = display_name(href, text,
                                            resp.headers.get("content-disposition", ""))
                        kind, hits, verdicts, ways = inspect(data, self.classify)
                        if kind and hits is None:
                            why = f"{kind} 문서를 해석하지 못함"
                        elif kind:
                            result = (name, kind, hits, verdicts, ways)
            except Exception as exc:
                result, why = None, f"받기 실패 ({type(exc).__name__})"
            if why:
                self.unread.append({"href": href, "reason": why})
            self.spent += time.perf_counter() - t0
        self.cache[href] = result
        if self.on_checkpoint: self.on_checkpoint()
        return result

    def check(self, page_url, links, prefix=""):
        """페이지의 첨부 링크 목록을 검사해 검출 건을 돌려준다."""
        rows = []
        for link in links:
            got = self._fetch(link["href"], link.get("text", ""))
            if not got or not got[2]:
                continue
            name, kind, hits, verdicts, ways = got
            hide = [w for w in ways if w != OCR_WAY]
            keywords = []
            for v in verdicts:
                keywords += [k for k in v["evidence"] if k not in keywords]
            shown = hits[:MAX_EVIDENCE]
            rows.append({
                "url": page_url, "location": prefix + link["selector"],
                "technique": "ETC",
                "evidence_text": f"[{name}] " + " / ".join(shown),
                "normalized": " / ".join(v["normalized"] for v in verdicts[:MAX_EVIDENCE]),
                "reason": f"첨부파일({KIND_NAMES.get(kind, kind)}) 본문 {len(hits)}곳에서 광고 문구"
                          + (" — 그림 속 글자를 글자 인식(OCR)으로 읽음" if OCR_WAY in ways else "")
                          + (f" — 문서 안에서 숨김: {', '.join(hide)}" if hide else ""),
                "hidden_in_file": hide,
                "keywords": keywords,
                "extra_finding": "ATTACHMENT_AD(첨부파일 내 광고)",
                "judgement": judge_many(verdicts, [f"문서 안에서 {w}" for w in hide]),
            })
        return rows
