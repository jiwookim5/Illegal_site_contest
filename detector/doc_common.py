"""첨부 문서에서 글자를 꺼내는 추출기들이 함께 쓰는 기준과 도구.

추출기마다 (문단 목록, 숨긴 글자 목록) 을 돌려준다. 숨긴 글자는 (글, 숨긴 방식) 이다.
웹 페이지와 같은 기준으로 문서 안에서도 '사람 눈에 안 보이게 넣은 글자'를 가린다.
"""
import re

MAX_BYTES = 20 * 1024 * 1024     # 이보다 큰 파일은 받지 않는다
OCR_WAY = "그림 속 글자(글자 인식으로 읽음)"

WHITE_MIN = 0.94      # 채움색 세 성분이 모두 이 이상이면 흰 바탕 위 흰 글씨로 본다
TINY_PT = 2.0         # 이 크기(pt) 이하 글자는 읽을 수 없다 (웹의 font-size 0~1px 와 같은 취지)


def hide_reasons(rgb=None, size_pt=None, invisible=False):
    """글자 모양으로 본 숨긴 방식 목록. rgb 는 0~1 세 성분."""
    out = []
    if invisible:
        out.append("보이지 않는 글자(PDF 렌더 모드 3)")
    if rgb is not None and min(rgb) >= WHITE_MIN:
        out.append("흰 글씨")
    if size_pt is not None and 0 < size_pt <= TINY_PT:
        out.append(f"글자 크기 {size_pt:.1f}pt")
    return out


def merge_runs(runs):
    """(글, 숨긴 방식) 조각들 가운데 숨긴 방식이 같은 이웃 조각을 이어 붙인다."""
    out = []
    for text, why in runs:
        if not why:
            out.append(None)
            continue
        if out and out[-1] is not None and out[-1][1] == why:
            out[-1] = (out[-1][0] + text, why)
        else:
            out.append((text, why))
    return [(" ".join(t.split()), w) for t, w in (r for r in out if r) if t.strip()]


def hex_rgb(v):
    m = re.fullmatch(r"#?([0-9A-Fa-f]{6})", (v or "").strip())
    if not m:
        return None
    h = m.group(1)
    return tuple(int(h[k:k + 2], 16) / 255 for k in (0, 2, 4))
