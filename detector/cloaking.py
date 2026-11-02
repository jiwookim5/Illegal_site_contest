"""크롤러에게만 다른 내용을 보여주는 위장(클로킹)을 찾아낸다.

불법광고는 '검색엔진에는 보이고 사람에게는 보이지 않는' 상태를 노린다.
가장 확실한 방법은 서버가 요청자를 보고 다른 응답을 주는 것이다.
같은 주소를 신원만 바꿔 한 번 더 조회해 응답을 비교하면 드러난다.

조회(GET)만 한다. 값을 넣어보거나 전송하는 동작은 하지 않는다.
"""
import re

import lexicon
from judgement import judge
from normalize import normalize

GOOGLEBOT_UA = ("Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)")
SEARCH_REFERER = "https://www.google.com/"

_TAG = re.compile(r"<(script|style)[^>]*>.*?</\1>", re.I | re.S)
_ANY_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def visible_text(html: str) -> str:
    """태그를 걷어낸 대략적인 본문. 응답 비교용이라 정밀할 필요는 없다."""
    text = _TAG.sub(" ", html or "")
    text = _ANY_TAG.sub(" ", text)
    return _WS.sub(" ", text).strip()


def _ad_terms(text: str):
    """이 문서에서 광고로 볼 만한 표현들을 모은다."""
    shown = visible_text(text)
    norm = normalize(shown)
    detail = lexicon.match_detail(norm, raw=shown)
    return (set(detail["evidence"]) if detail["is_ad"] else set()), norm, detail


def check(request_ctx, url, timeout_ms=10000):
    """(검출 목록) 을 돌려준다. 실패하면 빈 목록."""
    def fetch(headers):
        try:
            resp = request_ctx.get(url, headers=headers, timeout=timeout_ms)
            if not resp.ok:
                return None
            return resp.text()
        except Exception:
            return None

    human = fetch({})
    if human is None:
        return []

    human_terms, _, _ = _ad_terms(human)

    rows = []
    for label, headers in (
        ("검색엔진 크롤러", {"User-Agent": GOOGLEBOT_UA}),
        ("검색결과 유입", {"User-Agent": GOOGLEBOT_UA, "Referer": SEARCH_REFERER}),
    ):
        body = fetch(headers)
        if body is None:
            continue
        bot_terms, bot_norm, bot_detail = _ad_terms(body)

        # 사람에게 준 응답에는 없고 크롤러에게 준 응답에만 있는 광고 표현
        only_for_bot = bot_terms - human_terms
        if not only_for_bot:
            continue

        snippet = visible_text(body)
        marker = next((w for w in sorted(only_for_bot, key=len, reverse=True)
                       if w in normalize(snippet)), None)
        excerpt = snippet[:200]
        if marker:
            # 근거가 되는 대목을 우선 보여준다
            for part in re.split(r"(?<=[.!?。])\s+", snippet):
                if marker in normalize(part):
                    excerpt = part[:200]
                    break

        rows.append({
            "url": url,
            "location": "html",
            "technique": "ETC",
            "evidence_text": excerpt,
            "normalized": bot_norm[:200],
            "reason": f"{label} 신원으로 조회했을 때만 나타남: " + ", ".join(sorted(only_for_bot)),
            "keywords": sorted(only_for_bot),
            "extra_finding": "CLOAKING(크롤러 위장)",
            "judgement": judge({"score": bot_detail}, [f"{label}에게만 보여 줌"]),
        })
        break        # 한 페이지에 한 건이면 충분하다

    return rows
