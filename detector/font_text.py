"""Recover remapped web-font text only from exact bundled-reference outlines.

This is not OCR. Unknown or ambiguous shapes remain unchanged. Font family and
glyph names never establish a character's meaning. Network and parse budgets
are deliberately small; this path only examines same-origin font responses.
"""
from functools import lru_cache
from io import BytesIO
import struct
import time
from urllib.parse import urlsplit

from fontTools.pens.recordingPen import DecomposingRecordingPen
from fontTools.ttLib import TTFont
from runtime import asset_path

MAX_BYTES = 2 * 1024 * 1024
MAX_FONTS = 8
MAX_EXPANDED = 32 * 1024 * 1024
# woff2 는 윤곽 표(glyf)를 변환해 담아, 글자 하나를 읽으려 해도 표 전체를 순수 파이썬으로 다시 짠다.
# 정부 표준 글꼴 PretendardGOV(2MB, 23,410자)는 그것만 52초가 걸려, 교육부 누리집 점검이 첫 페이지에서
# '정체'로 멈췄다. 글자를 바꿔 치는 위장 글꼴은 필요한 글자만 담은 작은 글꼴이므로(시험 글꼴 13자)
# 글자가 이보다 많은 woff2 는 보지 않는다
MAX_WOFF2_GLYPHS = 4000


class BoundedPen(DecomposingRecordingPen):
    def __init__(self, glyphs):
        super().__init__(glyphs)
        self.components = 0
    def addComponent(self, glyphName, transformation, **kwargs):
        self.components += 1
        if self.components > 256:
            raise ValueError('Font component budget exceeded')
        return super().addComponent(glyphName, transformation, **kwargs)


def outline(glyphs, name, units):
    pen = BoundedPen(glyphs)
    glyphs[name].draw(pen)
    if not pen.value:
        return None
    points = [p for _, args in pen.value for p in args if p is not None]
    if not points:
        return None
    origin = (min(p[0] for p in points), min(p[1] for p in points))
    return tuple((op, tuple(None if p is None else tuple(round(round(v - origin[i]) / units, 6) for i, v in enumerate(p))
                           for p in points)) for op, points in pen.value)


@lru_cache(maxsize=1)
def reference_shapes():
    path = asset_path('fonts/PretendardVariable.woff2')
    if not path:
        return {}
    with TTFont(path, lazy=True) as font:
        glyphs = font.getGlyphSet(location={'wght': 400})
        cmap = font.getBestCmap()
        units = font['head'].unitsPerEm
        shapes = {}
        for code, name in cmap.items():
            if not 0xAC00 <= code <= 0xD7A3:
                continue
            key = outline(glyphs, name, units)
            if key:
                shapes.setdefault(key, set()).add(chr(code))
        return {shape: next(iter(chars)) for shape, chars in shapes.items() if len(chars) == 1}


def font_mapping(data):
    if not data or len(data) > MAX_BYTES:
        return {}
    if len(data) >= 20 and data[:4] in (b'wOFF', b'wOF2'):
        if struct.unpack_from('>I', data, 16)[0] > MAX_EXPANDED:
            return {}
    with TTFont(BytesIO(data), lazy=True) as font:
        if (sum(getattr(t, 'origLength', t.length) for t in font.reader.tables.values()) > MAX_EXPANDED or
                font['maxp'].numGlyphs > 40000):
            return {}
        if font.flavor == 'woff2' and font['maxp'].numGlyphs > MAX_WOFF2_GLYPHS:
            return {}
        cmap = font.getBestCmap() or {}
        candidates = [(cp, name) for cp, name in cmap.items()
                      if 33 <= cp <= 126 or 0xE000 <= cp <= 0xF8FF][:256]
        if not candidates:
            return {}
        glyphs = font.getGlyphSet(location={'wght': 400} if 'fvar' in font else None)
        ref = reference_shapes()
        units = font['head'].unitsPerEm
        mapped = {}
        deadline = time.monotonic() + 4
        for cp, name in candidates:
            if time.monotonic() > deadline:
                break
            char = ref.get(outline(glyphs, name, units))
            if char and char != chr(cp):
                mapped[chr(cp)] = char
        return mapped


class FontText:
    def __init__(self):
        self.data = {}
        self.maps = {}
        self.attempted = set()

    def route(self, route):
        request = route.request
        try:
            source = urlsplit(request.frame.url)
            target = urlsplit(request.url)
            if ((source.scheme, source.netloc) != (target.scheme, target.netloc) or
                    target.scheme not in ('http', 'https') or
                    len(self.attempted) >= MAX_FONTS and request.url not in self.data):
                route.abort()
                return
            if request.url in self.data:
                route.fulfill(body=self.data[request.url], content_type='application/octet-stream')
                return
            self.attempted.add(request.url)
            response = route.fetch(timeout=5000, max_redirects=0)
            if not response.ok or int(response.headers.get('content-length', '0')) > MAX_BYTES:
                route.abort()
                return
            data = response.body()
            if len(data) > MAX_BYTES:
                route.abort()
                return
            self.data[request.url] = data
            route.fulfill(response=response)
        except Exception:
            route.abort()

    def recover(self, node):
        for url in node.get('fontSources', []):
            if url not in self.data:
                continue
            if url not in self.maps:
                try:
                    self.maps[url] = font_mapping(self.data[url])
                except Exception:
                    self.maps[url] = {}
            mapping = self.maps[url]
            text = node['text']
            # Mixed fallback text is left intact; only proven glyph identities change.
            decoded = ''.join(mapping.get(ch, ch) for ch in text)
            if decoded != text:
                return dict(node, text=decoded, fontDecoded=True,
                            reasons=list(node.get('reasons', [])) + ['동봉 글꼴과 일치하는 윤곽으로 글꼴 치환 복원'])
        return node
