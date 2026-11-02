"""점검 대상 서버에 부담을 주지 않기 위한 장치.

이 도구는 각급 기관에 배포되어 담당자가 자기 누리집에 돌리게 된다.
자기 서버를 때리는 도구가 되지 않도록 요청 간격과 robots.txt 를 지킨다.
조회만 한다(GET). 폼 전송(POST)은 하지 않으며, 값을 넣는 것은 검색창 반사 점검에서
무해한 표식 문자열로 검색 폼마다 한 번 조회하는 것뿐이다. 예외로 '댓글 더보기'가 댓글 목록을
비동기 POST 로 불러올 때, 주소가 조회로 보이는 것만 보낸다 (js_links.is_read_post).
"""
import re
import time
import urllib.error
import urllib.request
from urllib.parse import unquote, urlparse

# HTTP 헤더는 latin-1 로만 보낼 수 있으므로 한글을 넣으면 요청 자체가 실패한다.
USER_AGENT = ("Mozilla/5.0 (compatible; PublicAdDetector/1.0; "
              "+public-website-illegal-ad-checker)")

DEFAULT_DELAY = 0.7        # 예의 모드에서 페이지 사이에 두는 간격(초)


class Robots:
    """robots.txt 규칙을 표준(RFC 9309)과 구글 방식대로 읽는다.

    파이썬 표준 해석기(urllib.robotparser)와 두 가지가 다르다.
    - 빈 줄에서 묶음을 끊지 않는다. 묶음은 규칙 줄 뒤에 다시 나온 User-agent 줄에서 끝난다
    - 위에서 처음 맞는 규칙이 아니라 가장 길게 맞는 규칙을 쓴다 (길이가 같으면 Allow)
    대전시 누리집은 'User-agent: *' 아래 'Disallow: /' 다음 빈 줄을 두고 'Allow: /drh'를 적었다.
    표준 해석기는 Allow 줄을 버리고 Disallow: / 만 남겨 허용된 게시판까지 한 쪽도 열지 않았다.
    """

    def __init__(self, text):
        self.groups = []           # ([User-agent 이름], [(규칙 길이, 허용 여부, 정규식)])
        agents, rules, in_rules = [], [], False
        for line in text.lstrip("\ufeff").splitlines():   # 파일 앞 BOM
            line = line.split("#", 1)[0].strip()
            if ":" not in line:
                continue
            key, value = (x.strip() for x in line.split(":", 1))
            key = key.lower()
            if key == "user-agent":
                if in_rules:
                    self.groups.append((agents, rules))
                    agents, rules, in_rules = [], [], False
                agents.append(value.lower())
            elif key in ("allow", "disallow") and agents:
                in_rules = True
                if value:              # 빈 Disallow 는 '모두 허용'이라 규칙이 없는 것과 같다
                    rules.append((len(value), key == "allow", self._pattern(value)))
            # Sitemap·Crawl-delay 같은 다른 줄은 묶음을 끊지 않는다
        if agents:
            self.groups.append((agents, rules))

    @staticmethod
    def _pattern(path):
        end = path.endswith("$")
        body = re.escape(unquote(path[:-1] if end else path)).replace(r"\*", ".*")
        return re.compile(body + ("$" if end else ""))

    def _rules_for(self, agent):
        tokens = set(re.findall(r"[a-z][a-z0-9_-]*", agent.lower()))
        named = [rules for names, rules in self.groups if any(n != "*" and n in tokens for n in names)]
        if named:                  # 같은 이름의 묶음이 여럿이면 합친다
            return [r for rules in named for r in rules]
        return [r for names, rules in self.groups if "*" in names for r in rules]

    def can_fetch(self, agent, url):
        parts = urlparse(url)
        target = unquote((parts.path or "/") + ("?" + parts.query if parts.query else ""))
        best = None
        for length, allow, pattern in self._rules_for(agent):
            if pattern.match(target) and (best is None or (length, allow) > best):
                best = (length, allow)
        return True if best is None else best[1]


class Politeness:
    """요청 간격과 robots.txt 준수를 담당한다."""

    def __init__(self, enabled=True, delay=DEFAULT_DELAY, respect_robots=True, exclusions=None):
        self.enabled = enabled
        self.delay = delay if enabled else 0.0
        self.respect_robots = respect_robots and enabled
        self._last = 0.0
        self._robots = {}      # origin -> Robots 또는 None
        self.skipped = []      # robots 로 걸러낸 주소
        self.exclusions = exclusions

    # ---- 간격 ----
    def wait(self):
        if self.delay <= 0:
            return
        gap = time.perf_counter() - self._last
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self._last = time.perf_counter()

    # ---- robots.txt ----
    def _parser_for(self, url):
        parts = urlparse(url)
        origin = f"{parts.scheme}://{parts.netloc}"
        if origin in self._robots:
            return self._robots[origin]
        parser = None
        try:
            req = urllib.request.Request(origin + "/robots.txt",
                                         headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=5) as resp:
                text = resp.read().decode("utf-8", "replace")
            parser = Robots(text)
        except Exception:
            parser = None          # 없거나 못 읽으면 제한 없음으로 본다
        self._robots[origin] = parser
        return parser

    def allowed(self, url):
        if self.exclusions and self.exclusions.skip(url):
            return False
        if not self.respect_robots:
            return True
        parser = self._parser_for(url)
        if parser is None:
            return True
        ok = parser.can_fetch(USER_AGENT, url)
        if not ok:
            self.skipped.append(url)
        return ok

    def robots_blocks(self, url, agent="Googlebot"):
        """검색엔진 크롤러가 이 주소를 수집하지 못하게 막혀 있는지.

        예의 모드와 상관없이 확인한다. 우리 요청을 거를지가 아니라
        '검색엔진이 이 주소를 읽을 수 있는가'를 판정하는 데 쓰기 때문이다.
        """
        parser = self._parser_for(url)
        return parser is not None and not parser.can_fetch(agent, url)

    def summary(self):
        return {
            "enabled": self.enabled,
            "delay": self.delay,
            "respect_robots": self.respect_robots,
            "skipped_by_robots": len(self.skipped),
        }
