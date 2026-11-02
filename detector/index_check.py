"""검색엔진에 이미 색인된 주소 가운데 광고가 노출되는 것을 찾는다.

검색결과 반사형 광고는 누리집 안 어디에도 링크되어 있지 않고 검색엔진 색인에만 있다.
그래서 링크를 따라가는 탐색으로는 닿을 수 없고, 색인 목록을 받아 하나씩 열어 봐야 한다.

입력
  Google Search Console 에서 내려받은 페이지 목록 CSV (실적 > 페이지, 색인 생성 > 페이지 등).
  내보내기 종류와 화면 언어마다 열 이름이 달라서 주소 열은 값을 보고 찾는다.
  주소만 한 줄에 하나씩 적은 텍스트 파일도 받는다.

판정 (주소 하나당 GET 한 번)
  피해 발생 또는 광고 확인됨  주소의 검색어 자리에 광고 문구가 있고, 그 문구가 지금도 제목·본문에 나타난다
             또는 주소와 무관하게 페이지 제목·본문에 광고 문구가 있다
  주의       광고 문구를 담은 주소가 색인되어 있으나 지금은 반사되지 않는다 (색인 잔존)
  그 밖에 검색어 파라미터가 붙은 주소인데 누리집 탐색에서 못 본 검색 경로라면
  검색창 반사 점검(search_reflect)에 넘겨 표식으로 한 번 조회한다.
"""
import csv
import io
import re
from scan_control import check_cancelled
from urllib.parse import parse_qsl, urlparse

from normalize import normalize
from search_reflect import page_info
from link_check import CONFIRMED

EXTRA_CODE = "SEARCH_INDEXED(검색엔진 색인 광고)"
MAX_URLS = 1000

_URL = re.compile(r"^https?://", re.I)
_NUMERIC = re.compile(r"^[\d\s.,:/-]*$")


def decode(data: bytes) -> str:
    """Search Console 은 UTF-8, 엑셀로 다시 저장하면 CP949 가 된다."""
    for enc in ("utf-8-sig", "cp949"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", "replace")


def parse_urls(text: str):
    """CSV 든 한 줄 목록이든 http(s) 주소를 순서대로(중복 없이) 뽑는다."""
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        return []
    # 주소가 가장 많이 들어 있는 열을 주소 열로 본다
    width = max(len(r) for r in rows)
    hits = [sum(1 for r in rows if i < len(r) and _URL.match(r[i].strip())) for i in range(width)]
    col = max(range(width), key=lambda i: hits[i])
    out, seen = [], set()
    for r in rows:
        if col < len(r):
            u = r[col].strip()
            if _URL.match(u) and u not in seen:
                seen.add(u)
                out.append(u)
    return out


def _same_site(host, origin):
    strip = lambda h: h[4:] if h.startswith("www.") else h
    return strip(host.lower()) == strip(origin.lower())


def search_params(url):
    """검색어로 보이는 파라미터들. 숫자·빈 값(페이지 번호, 게시글 번호)은 뺀다."""
    return [(k, v) for k, v in parse_qsl(urlparse(url).query, keep_blank_values=True)
            if v.strip() and not _NUMERIC.match(v)]


class IndexChecker:
    def __init__(self, reflect, classify):
        self.reflect = reflect          # 조회·예의·반사 점검을 함께 쓴다
        self.classify = classify
        self.checked = 0
        self.skipped_other_site = 0
        self.inspected = set()
        self.completed = set()
        self.later = {}
        self.saved_rows = []
        self.on_checkpoint = None

    def checkpoint(self):
        if self.on_checkpoint:
            self.on_checkpoint()

    def run(self, urls, entry_url):
        origin = urlparse(entry_url).netloc
        mine = [u for u in urls if _same_site(urlparse(u).netloc, origin)]
        self.skipped_other_site = len(urls) - len(mine)
        self.completed.update(set(urls) - set(mine))
        mine = [u for u in mine if u not in self.completed][:MAX_URLS]

        rows = self.saved_rows
        for url in mine:
            check_cancelled()
            if url in self.inspected:
                continue
            params = search_params(url)
            ad_params = [(k, v) for k, v in params if self.classify(v)["is_ad"]]
            row = self._check(url, ad_params)
            if row:
                rows.append(row)
                # 피해가 확인된 검색 기능은 반사 점검을 다시 할 필요가 없다
                for k, _ in ad_params:
                    self.reflect.seen.add(self.reflect.endpoint(url, k))
                self.completed.add(url)
            elif params:
                self.later[url] = params
            else:
                self.completed.add(url)
            self.inspected.add(url)
            self.checkpoint()

        # 색인 목록에서 처음 알게 된 검색 경로는 표식으로 반사 여부를 본다
        for url, params in self.later.items():
            if url in self.completed:
                continue
            check_cancelled()
            for k, _ in params:
                r = self.reflect.check_url(url, k)
                if r:
                    rows.append(r)
                    break
            self.completed.add(url)
            self.checkpoint()
        return rows

    def _check(self, url, ad_params):
        got = self.reflect.fetch(url)
        self.checked += 1
        if got is None:
            return None
        info = page_info(*got)
        title_n, text_n = normalize(info["title"]), normalize(info["text"])

        where, words = [], []
        for _, v in ad_params:
            v_n = normalize(v)
            if v_n in title_n and "제목" not in where:
                where.append("제목")
            if v_n in text_n and "본문" not in where:
                where.append("본문")
            words += self.classify(v)["evidence"]

        if not ad_params:
            # 검색어와 무관하게 페이지 자체에 광고가 있는 경우 (색인된 스팸 게시글 등)
            for label, text in (("제목", info["title"]), ("본문", info["text"])):
                v = self.classify(text)
                if v["is_ad"]:
                    where.append(label)
                    words += v["evidence"]
            if not where:
                return None

        ad_text = " / ".join(v for _, v in ad_params)
        blocked = ", ".join(info["noindex"])
        if where:
            grade = CONFIRMED
            how = (f"주소에 담긴 광고 문구가 {'·'.join(where)}에 그대로 나타남" if ad_params
                   else f"페이지 {'·'.join(where)}에 광고 문구가 있음")
            guide = ("Search Console 의 '삭제' 도구로 이 주소의 색인 삭제를 요청하십시오."
                     + (" 이 페이지에는 이미 noindex 가 있어 새로 색인되지는 않습니다." if blocked else
                        " 같은 수법이 반복되지 않도록 이 검색결과 페이지에 noindex 를 넣으십시오."
                        if ad_params else " 해당 게시물을 삭제하십시오."))
        else:
            grade = "주의"
            how = "광고 문구를 담은 주소가 색인되어 있으나 지금은 페이지에 나타나지 않음(색인 잔존)"
            guide = ("검색 결과에는 예전 제목이 남아 있을 수 있습니다. "
                     "Search Console 의 '삭제' 도구로 이 주소의 색인 삭제를 요청하십시오.")

        location = "title" if "제목" in where else "body" if where else "html"
        evidence = f"[{grade}] 검색엔진에 색인된 주소에서 {how}."
        if ad_params:
            evidence += f" 검색어: '{ad_text[:80]}'"
        if "제목" in where:
            evidence += f" 제목: '{info['title'][:80]}'"
        return {
            "url": url, "location": location, "technique": "ETC",
            "normalized": normalize(ad_text)[:200] if ad_params else "",
            "extra_finding": EXTRA_CODE, "is_violation": grade == CONFIRMED,
            "grade": grade, "keywords": sorted(set(words)),
            "reason": how + (f" (현재 {blocked})" if blocked else ", 색인 차단 없음"),
            "evidence_text": evidence, "guide": guide,
        }
