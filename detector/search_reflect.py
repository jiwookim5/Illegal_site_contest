"""검색창이 '검색결과 반사형' 불법광고에 악용될 수 있는지 점검한다.

악용 방식
  기관 누리집 검색창에 광고 문구를 넣으면 '<문구> 검색결과' 페이지가 만들어진다.
  그 주소를 외부에서 대량으로 링크하면 검색엔진이 go.kr 페이지로 색인하고,
  도박 키워드 검색 결과에 기관 도메인이 광고 문구를 제목으로 달고 뜬다.
  서버에는 아무것도 저장되지 않으므로 게시판을 뒤져도 흔적이 없다.

점검 방식
  검색 폼마다 한 번, 광고가 아닌 무해한 표식 문자열로 GET 조회한다.
  표식이 제목·본문에 그대로 나오는지, 색인 차단(noindex)이 있는지 본다.
  POST 폼은 전송하지 않는다. 검색엔진도 POST 결과는 색인하지 못하므로 점검 대상이 아니다.

등급
  취약  제목에 반사되고 색인 차단이 없다 (검색 결과 제목에 광고가 뜬다)
  주의  본문에만 반사되거나, canonical 로 다른 주소를 가리키거나,
        robots.txt 로 수집만 막혀 있다 (robots.txt 는 주소 자체의 색인은 막지 못한다)
  안전  noindex(메타 태그 또는 X-Robots-Tag 헤더)로 색인이 막혀 있다 -> 보고하지 않는다
"""
import html
import re
import secrets
from urllib.parse import parse_qsl, urlencode, urljoin, urlparse

from cloaking import visible_text

EXTRA_CODE = "SEARCH_REFLECT(검색결과 반사 취약)"

_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)
_BODY = re.compile(r"<body[^>]*>(.*)</body>", re.I | re.S)
_META = re.compile(r"<meta\b[^>]*>", re.I)
_LINK = re.compile(r"<link\b[^>]*>", re.I)
_ATTR = re.compile(r"""([\w:-]+)\s*=\s*(?:"([^"]*)"|'([^']*)'|([^\s>]+))""")

GUIDE = {
    "취약": "검색결과 페이지에 <meta name=\"robots\" content=\"noindex\"> 를 넣거나 "
            "X-Robots-Tag: noindex 헤더를 보내 색인을 막으십시오.",
    "주의": "지금 당장 제목에 뜨지는 않지만 색인은 막혀 있지 않습니다. "
            "검색결과 페이지에 noindex 를 넣는 것이 안전합니다.",
}


def tag_attrs(tag):
    """HTML 태그 글자 하나에서 속성 이름(소문자)과 값."""
    return {m.group(1).lower(): html.unescape(m.group(2) or m.group(3) or m.group(4) or "")
            for m in _ATTR.finditer(tag)}


def page_info(body, headers, final_url):
    """응답 한 건에서 제목·본문 글자·색인 차단·canonical 을 읽는다."""
    m = _TITLE.search(body)
    title = html.unescape(m.group(1)).strip() if m else ""
    m = _BODY.search(body)
    text = visible_text(m.group(1) if m else body)

    noindex = []
    for tag in _META.findall(body):
        a = tag_attrs(tag)
        if a.get("name", "").lower() in ("robots", "googlebot") and "noindex" in a.get("content", "").lower():
            noindex.append("meta robots noindex")
    header = next((v for k, v in headers.items() if k.lower() == "x-robots-tag"), "")
    if "noindex" in header.lower():
        noindex.append("X-Robots-Tag: noindex")

    canonical = None
    for tag in _LINK.findall(body):
        a = tag_attrs(tag)
        if "canonical" in a.get("rel", "").lower().split() and a.get("href"):
            canonical = urljoin(final_url, a["href"])
    return {"title": title, "text": text, "noindex": noindex, "canonical": canonical}


def inspect(body, headers, final_url, marker):
    """표식이 제목·본문 어디에 반사되는지와 색인 차단 여부."""
    info = page_info(body, headers, final_url)
    low = marker.lower()
    canonical = info["canonical"]
    return dict(info,
                in_title=low in info["title"].lower(),
                in_body=low in info["text"].lower(),
                # canonical 이 검색어 없는 다른 주소를 가리키면 검색엔진이 그쪽을 대표로 삼을 수 있다
                canonical_elsewhere=bool(canonical) and low not in canonical.lower())


def grade(info):
    """(등급, 근거 목록). 반사가 없거나 색인이 막혀 있으면 등급은 None."""
    if not (info["in_title"] or info["in_body"]) or info["noindex"]:
        return None, []
    where = ["제목(<title>)" if info["in_title"] else None, "본문" if info["in_body"] else None]
    why = [f"검색어가 {' · '.join(w for w in where if w)}에 그대로 나타남", "색인 차단(noindex) 없음"]
    if info["in_title"] and not info["canonical_elsewhere"]:
        return "취약", why
    if info["canonical_elsewhere"]:
        why.append(f"canonical 이 {info['canonical']} 을 가리킴 (검색엔진이 따르지 않을 수 있음)")
    return "주의", why


class SearchReflectScanner:
    """검색 폼을 모아 (주소, 검색어 이름) 단위로 한 번씩만 조회한다."""

    def __init__(self, request_ctx, manners, timeout_ms=10000):
        self.request = request_ctx
        self.manners = manners
        self.timeout_ms = timeout_ms
        # 광고 사전에 걸리지 않고 페이지에 우연히 있을 수 없는 문자열
        self.marker = "hwonhi" + secrets.token_hex(4)
        self.seen = set()
        self.probed = 0

    @staticmethod
    def endpoint(url, param):
        """같은 검색 기능을 가리키는 키. (호스트, 경로, 검색어 파라미터 이름)"""
        u = urlparse(url)
        return (u.netloc, u.path.rstrip("/"), param)

    def fetch(self, url):
        """GET 한 번. (본문, 헤더, 최종 주소) 또는 None. 예의 모드 간격을 지킨다."""
        if not self.manners.allowed(url):
            return None
        self.manners.wait()
        self.probed += 1
        try:
            resp = self.request.get(url, timeout=self.timeout_ms)
            if not resp.ok or "html" not in resp.headers.get("content-type", "html"):
                return None
            return resp.text(), resp.headers, resp.url
        except Exception:
            return None

    def probe_url(self, form):
        action = urlparse(form["action"])
        params = [(f["name"], self.marker if f["name"] == form["texts"][0] else f["value"])
                  for f in form["fields"]]
        # GET 폼은 action 의 기존 쿼리를 버리고 폼 값으로 새로 만든다 (브라우저 동작과 같다)
        return action._replace(query=urlencode(params), fragment="").geturl()

    def check(self, url, forms, prefix=""):
        origin = urlparse(url).netloc
        rows = []
        for form in forms:
            if form["method"] != "get":
                continue                    # POST 는 전송하지 않는다
            action = urlparse(form["action"])
            if action.scheme not in ("http", "https") or action.netloc != origin:
                continue                    # 바깥 사이트(포털 검색 등)로 보내는 폼은 조회하지 않는다
            key = self.endpoint(form["action"], form["texts"][0])
            if key in self.seen:
                continue                    # 모든 페이지 머리에 있는 통합검색은 처음 한 번만
            self.seen.add(key)
            row = self._check_one(url, prefix + form["selector"], self.probe_url(form))
            if row:
                rows.append(row)
        return rows

    def check_url(self, url, param):
        """폼 없이 주소만 아는 검색 기능을 점검한다 (색인 목록에서 찾은 숨은 검색 경로).

        다른 파라미터는 그대로 두고 검색어 자리만 표식으로 바꿔 조회한다.
        """
        key = self.endpoint(url, param)
        if key in self.seen:
            return None
        self.seen.add(key)
        u = urlparse(url)
        params = [(k, self.marker if k == param else v)
                  for k, v in parse_qsl(u.query, keep_blank_values=True)]
        probe = u._replace(query=urlencode(params), fragment="").geturl()
        return self._check_one(url, "html", probe, found_by="검색엔진 색인 목록에서 찾은 ")

    def _check_one(self, url, location, probe, found_by=""):
        shown = probe.replace(self.marker, "<검색어>")
        base = {
            "url": url, "location": location, "technique": "ETC",
            "normalized": "", "extra_finding": EXTRA_CODE, "is_violation": False,
        }

        if self.manners.robots_blocks(probe):
            # 검색엔진이 못 읽으니 조회할 필요도 없다. 다만 주소 자체는 외부 링크로 색인될 수 있다.
            return dict(base, grade="주의", keywords=["robots.txt 차단만 있음"],
                        reason="robots.txt 로 수집만 막혀 있음. 외부 링크가 많으면 "
                               "주소와 링크 문구만으로 검색 결과에 뜰 수 있음",
                        evidence_text=f"[주의] {found_by}검색 주소 {shown} 는 robots.txt 로 수집이 막혀 있으나 "
                                      "noindex 가 아니므로 색인 자체는 막지 못함",
                        guide="robots.txt 차단 대신 검색결과 페이지에 noindex 를 넣으십시오. "
                              "noindex 는 검색엔진이 페이지를 읽어야 적용되므로 robots.txt 차단은 풀어야 합니다.")
        got = self.fetch(probe)
        if got is None:
            return None
        info = inspect(*got, self.marker)

        level, why = grade(info)
        if level is None:
            return None
        title = info["title"].replace(self.marker, "<검색어>")
        detail = f" 제목: '{title[:80]}'" if info["in_title"] else ""
        return dict(base, grade=level, keywords=why,
                    reason=", ".join(why),
                    evidence_text=f"[{level}] {found_by}검색 주소 {shown} 조회 시 " + ", ".join(why) + "." + detail,
                    guide=GUIDE[level])
