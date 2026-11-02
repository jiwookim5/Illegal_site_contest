"""글꼴 바꿔치기 시험용 글꼴 (testsite_evasion/files/remap.woff).

영문 소문자 a~k 자리에 '카지노가입문의텔레그램' 글자 모양을 넣는다. 소스에는 'abc', 화면에는 '카지노'.
Pretendard(OFL)에서 만들므로 예약 이름 Pretendard 를 쓰지 않고 HwonhiRemapTest 로 바꾼다.

    pip install fonttools brotli
    python tools/make_remap_font.py assets/fonts/PretendardVariable.woff2 testsite_evasion/files/remap.woff
"""
import sys
from fontTools.ttLib import TTFont
from fontTools import subset
from fontTools.varLib import instancer
SRC, OUT = sys.argv[1], sys.argv[2]
MAP = dict(zip("abcdefghijk", "카지노가입문의텔레그램"))
f = TTFont(SRC)
if "fvar" in f:
    f = instancer.instantiateVariableFont(f, {"wght": 400})
cmap = f.getBestCmap()
glyph = {k: cmap[ord(v)] for k, v in MAP.items()}
opts = subset.Options(); opts.flavor = "woff"; opts.layout_features = []; opts.name_IDs = ["*"]; opts.notdef_outline = True
sub = subset.Subsetter(opts)
sub.populate(unicodes=[ord(v) for v in MAP.values()] + [0x20])
sub.subset(f)
for t in f["cmap"].tables:
    if t.isUnicode():
        for k, g in glyph.items():
            t.cmap[ord(k)] = g
        for v in MAP.values():
            t.cmap.pop(ord(v), None)
# OFL: 고친 글꼴은 예약 이름(Pretendard)을 쓰면 안 된다. 저작권(0)·라이선스(13·14) 표시는 남긴다
NEW = "HwonhiRemapTest"
name = f["name"]
for rec in list(name.names):
    if rec.nameID in (1, 3, 4, 6, 16, 17, 21, 22, 25):
        name.removeNames(nameID=rec.nameID)
for nid, val in ((1, NEW), (2, "Regular"), (3, NEW + "-Regular"), (4, NEW), (6, NEW + "-Regular")):
    name.setName(val, nid, 3, 1, 0x409)
f.flavor = "woff"
f.save(OUT)
print("ok", OUT)
