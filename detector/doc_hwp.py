"""한글 문서(HWP 5.0 바이너리·HWPX)에서 글자와 숨긴 글자를 꺼낸다."""
import io
import re
import struct
import zipfile
import zlib
from xml.etree import ElementTree

from doc_common import hex_rgb, hide_reasons, merge_runs

HWPTAG_PARA_TEXT = 0x10 + 51
# 한글 문서 본문 속 제어 문자. 글자 1칸짜리 외에는 8칸(16바이트)을 차지한다.
_CHAR_CTRL = {0, 10, 13} | set(range(24, 32))


def _hwp_chars(raw):
    """PARA_TEXT 를 (코드 위치, 글자) 목록으로. 위치는 글자 모양 표(PARA_CHAR_SHAPE)가 쓰는 단위다."""
    out, i, n = [], 0, len(raw) // 2
    codes = struct.unpack(f"<{n}H", raw[:n * 2])
    while i < n:
        c = codes[i]
        if c >= 32:
            out.append((i, chr(c)))
            i += 1
        elif c in _CHAR_CTRL:
            if c in (10, 13):
                out.append((i, "\n"))
            i += 1
        else:
            i += 8
    return out


HWPTAG_CHAR_SHAPE = 0x10 + 5
HWPTAG_PARA_CHAR_SHAPE = 0x10 + 52


def _hwp_char_shapes(docinfo):
    """DocInfo 의 글자 모양들 -> 번호마다 숨긴 방식. 기준 크기(1/100pt)와 글자색(0x00BBGGRR)만 본다."""
    shapes = []
    for tag, body in _hwp_records(docinfo):
        if tag != HWPTAG_CHAR_SHAPE or len(body) < 56:
            continue
        size, = struct.unpack_from("<i", body, 42)
        color, = struct.unpack_from("<I", body, 52)
        rgb = tuple(((color >> s) & 0xFF) / 255 for s in (0, 8, 16))
        shapes.append(tuple(hide_reasons(rgb, size / 100)))
    return shapes


def _hwp_records(stream):
    pos, n = 0, len(stream)
    while pos + 4 <= n:
        head, = struct.unpack_from("<I", stream, pos)
        pos += 4
        tag, size = head & 0x3FF, (head >> 20) & 0xFFF
        if size == 0xFFF:
            if pos + 4 > n:
                return
            size, = struct.unpack_from("<I", stream, pos)
            pos += 4
        yield tag, stream[pos:pos + size]
        pos += size


def hwp_paragraphs(data):
    import olefile

    ole = olefile.OleFileIO(io.BytesIO(data))
    try:
        header = ole.openstream("FileHeader").read(256)
        if not header.startswith(b"HWP Document File"):
            return [], []
        props, = struct.unpack_from("<I", header, 36)
        compressed, encrypted = bool(props & 1), bool(props & 2)

        def stream(name):
            raw = ole.openstream(name).read()
            if compressed:
                raw = zlib.decompressobj(-15).decompress(raw)
            return raw

        out, runs = [], []
        if not encrypted:
            shapes = []
            if ole.exists("DocInfo"):
                try:
                    shapes = _hwp_char_shapes(stream("DocInfo"))
                except (zlib.error, struct.error):
                    shapes = []
            sections = sorted(
                (e for e in ole.listdir() if len(e) == 2 and e[0] == "BodyText"),
                key=lambda e: int(re.sub(r"\D", "", e[1]) or 0))
            for entry in sections:
                try:
                    raw = stream(entry)
                except zlib.error:
                    continue
                chars = []
                for tag, body in _hwp_records(raw):
                    if tag == HWPTAG_PARA_TEXT:
                        chars = _hwp_chars(body)
                        out.extend("".join(ch for _, ch in chars).split("\n"))
                    elif tag == HWPTAG_PARA_CHAR_SHAPE and chars and shapes:
                        # (시작 위치, 글자 모양 번호) 쌍. 다음 시작 위치 전까지 그 모양이다
                        pairs = [struct.unpack_from("<II", body, k) for k in range(0, len(body) - 7, 8)]
                        for j, (pos, sid) in enumerate(pairs):
                            end = pairs[j + 1][0] if j + 1 < len(pairs) else 1 << 30
                            why = shapes[sid] if sid < len(shapes) else ()
                            runs.append(("".join(ch for i, ch in chars if pos <= i < end), why))
                        chars = []
        # 암호·배포용 문서는 본문이 잠겨 있다. 미리보기 글자라도 본다.
        if not out and ole.exists("PrvText"):
            prv = ole.openstream("PrvText").read().decode("utf-16-le", "ignore")
            out = prv.replace("\x00", "").splitlines()
        return out, merge_runs(runs)
    finally:
        ole.close()


def hwpx_paragraphs(data):
    def local(tag):
        return tag.rsplit("}", 1)[-1]

    out, runs = [], []
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        # 글자 모양(charPr): 번호 -> 숨긴 방식. 크기(height)는 1/100pt, 색은 #RRGGBB
        shapes = {}
        if "Contents/header.xml" in z.namelist():
            try:
                for el in ElementTree.fromstring(z.read("Contents/header.xml")).iter():
                    if local(el.tag) == "charPr" and el.get("id") is not None:
                        try:
                            size = int(el.get("height") or 0) / 100
                        except ValueError:
                            size = None
                        shapes[el.get("id")] = tuple(hide_reasons(hex_rgb(el.get("textColor")), size))
            except ElementTree.ParseError:
                shapes = {}
        names = sorted(n for n in z.namelist()
                       if re.match(r"Contents/section\d+\.xml$", n))
        for name in names:
            root = ElementTree.fromstring(z.read(name))
            for p in root.iter():
                if local(p.tag) != "p":
                    continue
                # 표 안의 문단은 따로 순회되므로 이 문단의 글자만 모은다
                parts = []
                for run in p:
                    if local(run.tag) != "run":
                        continue
                    text = "".join("".join(t.itertext()) for t in run if local(t.tag) == "t")
                    parts.append(text)
                    runs.append((text, shapes.get(run.get("charPrIDRef"), ())))
                out.append("".join(parts))
    return out, merge_runs(runs)
