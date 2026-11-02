"""PDF 와 그림 파일에서 글자를 꺼낸다.

글자층은 pypdf 로 꺼내면서 그리기 상태(채움색·글자 크기·렌더 모드)를 따라가 숨긴 글자를 가린다.
글자층이 없는 스캔 페이지와 그림 파일은 Windows 글자 인식(ocr.py)으로 읽는다.
"""
import io
import re
import struct

import ocr
from doc_common import OCR_WAY, hide_reasons, merge_runs

MAX_PDF_PAGES = 60


def _mat_mul(a, b):
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


def _pdf_rgb(op, args):
    """채움색 연산자의 값을 0~1 RGB 로. 알 수 없는 색 공간이면 None."""
    try:
        v = [float(x) for x in args]
    except (TypeError, ValueError):
        return None
    if op == b"g" or (op in (b"sc", b"scn") and len(v) == 1):
        return (v[0],) * 3
    if op == b"rg" or (op in (b"sc", b"scn") and len(v) == 3):
        return tuple(v[:3])
    if op == b"k" or (op in (b"sc", b"scn") and len(v) == 4):
        c, m, y, k = v
        return ((1 - c) * (1 - k), (1 - m) * (1 - k), (1 - y) * (1 - k))
    return None


SCAN_TEXT_MIN = 20       # 글자가 이보다 적은 PDF 페이지는 스캔한 것으로 보고 그림을 읽는다
SCAN_IMAGES_MAX = 10     # 문서 하나에서 글자 인식으로 읽을 그림 수


def _pdf_images(page):
    """페이지에 그린 그림을 글자 인식이 읽을 수 있는 그림 파일 바이트로. Pillow 없이 직접 꺼낸다.

    JPEG(DCTDecode)는 압축된 데이터가 곧 JPEG 파일이다. 압축만 푼 8비트 RGB·회색 픽셀(FlateDecode)은
    BMP 머리를 붙인다. 팩스식 흑백 압축(CCITT·JBIG2)·JPEG2000 은 건너뛴다.
    """
    try:
        xobjs = page["/Resources"].get("/XObject") or {}
    except Exception:
        return
    for ref in xobjs.values():
        try:
            x = ref.get_object()
            if x.get("/Subtype") != "/Image":
                continue
            filters = x.get("/Filter")
            filters = [str(f) for f in (filters if isinstance(filters, list) else [filters] if filters else [])]
            if filters and filters[-1] == "/DCTDecode":
                if filters == ["/DCTDecode"]:
                    yield x._data
                continue
            if any(f in ("/CCITTFaxDecode", "/JBIG2Decode", "/JPXDecode") for f in filters):
                continue
            w, h = int(x["/Width"]), int(x["/Height"])
            bpc = int(x.get("/BitsPerComponent", 8))
            cs = str(x.get("/ColorSpace"))
            comps = {"/DeviceRGB": 3, "/DeviceGray": 1}.get(cs)
            if bpc != 8 or not comps:
                continue
            yield _bmp(x.get_data(), w, h, comps)
        except Exception:
            continue


def _bmp(pixels, w, h, comps):
    """8비트 RGB·회색 픽셀(위에서 아래로)을 24비트 BMP 로."""
    row = (w * 3 + 3) & ~3
    body = bytearray()
    for y in range(h - 1, -1, -1):               # BMP 는 아래 줄부터
        src = pixels[y * w * comps:(y + 1) * w * comps]
        line = bytearray(w * 3)
        if len(src) < w * comps:
            src = src + b"\x00" * (w * comps - len(src))
        if comps == 1:
            line[0::3] = line[1::3] = line[2::3] = src
        else:                                    # RGB -> BGR
            line[0::3], line[1::3], line[2::3] = src[2::3], src[1::3], src[0::3]
        body += line + b"\x00" * (row - w * 3)
    head = struct.pack("<2sIHHI", b"BM", 54 + len(body), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(body), 2835, 2835, 0, 0)
    return head + info + bytes(body)


RENDER_DPI = 200          # 스캔 페이지를 그릴 해상도. 글자 인식은 글자 높이 20~30 픽셀에서 잘 된다
RENDER_MAX_SIDE = 4000    # 그린 그림의 긴 변 상한 (큰 도면 등)


def _ocr_scanned_page(data, page_no, page, scanned, budget, renderer):
    """글자층이 없는 페이지를 글자 인식으로 읽는다.

    PDFium(pypdfium2)이 있으면 페이지를 통째로 그려 읽는다. 팩스식 흑백 압축(CCITT·JBIG2)·JPEG2000 그림이나
    글자를 도형으로 그린 페이지도 읽을 수 있다. 없으면 페이지 안 그림(JPEG·무압축)을 직접 꺼내 읽는다.
    """
    if not ocr.available():
        return []
    try:
        import pypdfium2 as pdfium
    except ImportError:
        return _ocr_page_images(page, budget) if scanned else []
    try:
        if "doc" not in renderer:
            renderer["doc"] = pdfium.PdfDocument(data)
        pg = renderer["doc"][page_no]
        w, h = pg.get_size()
        # 그림의 원래 해상도보다 크게 그리면 흑백 스캔의 글자 가장자리가 계단처럼 깨져 인식이 틀린다.
        # 그림이 있으면 그 해상도(배율)까지만 그리고, 없으면(글자를 도형으로 그린 페이지) 200dpi 로 그린다.
        native = _image_scale(page, w)
        scale = min(RENDER_DPI / 72, RENDER_MAX_SIDE / max(w, h, 1), max(native or RENDER_DPI / 72, 1.0))
        bitmap = pg.render(scale=scale)
        if bitmap.mode != "BGR":
            return []
        budget[0] -= 1
        lines = ocr.read_lines(_bmp_bgr(bitmap.buffer, bitmap.width, bitmap.height, bitmap.stride))
    except Exception:
        return []
    return [" ".join(lines)] if lines else []


def _image_scale(page, page_width):
    """페이지에서 가장 큰 그림의 '그림 픽셀 / 페이지 포인트' 배율. 그림이 없으면 None."""
    try:
        xobjs = page["/Resources"].get("/XObject") or {}
        widths = [int(x.get_object()["/Width"]) for x in xobjs.values()
                  if x.get_object().get("/Subtype") == "/Image"]
    except Exception:
        return None
    return max(widths) / page_width if widths and page_width else None


def _bmp_bgr(buf, w, h, stride):
    """BGR 픽셀(위에서 아래로, 줄마다 stride 바이트)을 24비트 BMP 로. BMP 는 아래 줄부터 쓴다."""
    row = (w * 3 + 3) & ~3
    mv = memoryview(buf)
    pad = b"\x00" * (row - w * 3)
    body = b"".join(bytes(mv[y * stride:y * stride + w * 3]) + pad for y in range(h - 1, -1, -1))
    head = struct.pack("<2sIHHI", b"BM", 54 + len(body), 0, 0, 54)
    info = struct.pack("<IiiHHIIiiII", 40, w, h, 1, 24, 0, len(body), 2835, 2835, 0, 0)
    return head + info + body


def _ocr_page_images(page, budget):
    """스캔 페이지의 그림을 글자 인식으로 읽는다. 그림마다 한 문단."""
    out = []
    if not ocr.available():
        return out
    for data in _pdf_images(page):
        if budget[0] <= 0:
            break
        if not ocr.image_kind(data):
            continue
        budget[0] -= 1
        lines = ocr.read_lines(data)
        if lines:
            out.append(" ".join(lines))
    return out


def image_paragraphs(data):
    """첨부한 그림 파일(포스터·배너·스캔 그림). 글자 인식으로 읽어 한 문단으로 본다."""
    lines = ocr.read_lines(data)
    if not lines:
        return [], []
    text = " ".join(lines)
    return [text], [(text, (OCR_WAY,))]


def _has_image(page):
    try:
        xobjs = page["/Resources"].get("/XObject") or {}
        return any(x.get_object().get("/Subtype") == "/Image" for x in xobjs.values())
    except Exception:
        return False


def pdf_paragraphs(data):
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        try:
            reader.decrypt("")      # 열기 암호 없이 권한만 걸린 문서
        except Exception:
            return [], []
    out, runs = [], []
    scan_budget = [SCAN_IMAGES_MAX]
    renderer = {}                # 스캔 페이지를 그릴 PDFium 문서 (처음 필요할 때 연다)
    for page_no, page in enumerate(reader.pages[:MAX_PDF_PAGES]):
        # 글자를 꺼내면서 그리기 상태(채움색·렌더 모드)를 따라간다. q/Q 로 저장·복원된다.
        state = {"rgb": (0.0, 0.0, 0.0), "mode": 0}
        stack = []
        # 스캔 문서는 그림 위에 '보이지 않는 글자'(렌더 모드 3)로 검색용 글자층을 덮는다.
        # 그림이 있는 페이지의 렌더 모드 3 은 숨김이 아니다.
        scanned = _has_image(page)

        def before(op, args, cm, tm):
            if op == b"q":
                stack.append(dict(state))
            elif op == b"Q" and stack:
                state.update(stack.pop())
            elif op in (b"g", b"rg", b"k", b"sc", b"scn"):
                rgb = _pdf_rgb(op, args)
                if rgb is not None:
                    state["rgb"] = rgb
            elif op == b"Tr" and args:
                try:
                    state["mode"] = int(args[0])
                except (TypeError, ValueError):
                    pass

        def on_text(text, cm, tm, font_dict, font_size):
            if not text:
                return
            try:
                m = _mat_mul(list(tm), list(cm))
                size = float(font_size) * (m[2] ** 2 + m[3] ** 2) ** 0.5
            except Exception:
                size = None
            runs.append((text, tuple(hide_reasons(state["rgb"], size, state["mode"] == 3 and not scanned))))

        try:
            text = page.extract_text(visitor_operand_before=before, visitor_text=on_text) or ""
        except Exception:
            continue
        if len(text.strip()) < SCAN_TEXT_MIN and scan_budget[0] > 0:
            for line in _ocr_scanned_page(data, page_no, page, scanned, scan_budget, renderer):
                out.append(line)
                runs.append((line, (OCR_WAY,)))
                runs.append(("", ()))
            continue
        # PDF 는 줄바꿈이 조판 결과일 뿐이다. 빈 줄만 문단 경계로 본다.
        for block in re.split(r"\n\s*\n", text):
            out.append(" ".join(block.split()))
    if renderer.get("doc") is not None:
        renderer["doc"].close()
    return out, merge_runs(runs)
