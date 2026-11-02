"""담당자가 확인한 URL만 다음 점검에서 제외한다."""
from urllib.parse import urljoin, urlsplit, urlunsplit


class ExcludedNavigation(Exception):
    pass


def exclusion_key(url):
    """호스트·기본 포트·fragment만 정규화한다. 경로와 쿼리는 넓혀 잡지 않는다."""
    if not isinstance(url, str) or any(ord(c) < 33 for c in url):
        raise ValueError("제외 주소는 올바른 http/https URL이어야 합니다.")
    p = urlsplit(url)
    if p.scheme.lower() not in ("http", "https") or not p.hostname or p.username or p.password:
        raise ValueError("제외 주소는 인증 정보가 없는 http/https URL이어야 합니다.")
    host = p.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    port = p.port
    if port is not None and port != (443 if p.scheme.lower() == "https" else 80):
        host += f":{port}"
    return urlunsplit((p.scheme.lower(), host, p.path or "/", p.query, ""))


class ScanExclusions:
    """실행 시작 시 복사한 제외 목록과 이번 실행에서 만난 제외 주소."""

    def __init__(self, rows=()):
        self.rules = {exclusion_key(r["url"]): dict(r) for r in rows}
        self.skipped = {}
        self.blocked_navigation = False
        self.hits = 0

    def contains(self, url):
        try:
            return exclusion_key(url) in self.rules
        except (ValueError, TypeError):
            return False

    def skip(self, url):
        if not self.contains(url):
            return False
        key = exclusion_key(url)
        self.hits += 1
        self.skipped.setdefault(key, dict(self.rules[key], url=url))
        return True

    def attach(self, context):
        if not self.rules:
            return
        context._hwonhi_exclusions = self

        def guard(route):
            if self.skip(route.request.url):
                if route.request.is_navigation_request() and route.request.frame.parent_frame is None:
                    self.blocked_navigation = True
                route.abort("blockedbyclient")
            else:
                route.fallback()
        context.route("**/*", guard)

    def open(self, session, url, **options):
        self.blocked_navigation = False
        if self.skip(url):
            raise ExcludedNavigation(url)
        try:
            status = session.open(url, **options)
        except Exception:
            if self.blocked_navigation:
                raise ExcludedNavigation(url) from None
            raise
        if self.blocked_navigation or self.skip(session.page.url):
            raise ExcludedNavigation(url)
        return status

    def rules_within(self, allows):
        """allows(url)이 참인 규칙 수. 다른 누리집용 규칙은 이번 점검에 적용된 것으로 세지 않는다."""
        return sum(1 for key in self.rules if allows(key))

    def request(self, context):
        """APIRequestContext 대체. 브라우저 route를 거치지 않는 직접 조회도 제외 주소와 그쪽으로의
        리다이렉트를 ExcludedNavigation 으로 막는다. 조회 메서드 전부가 같은 검사를 거친다."""
        if not self.rules:
            return context
        exclusions = self

        class Requests:
            def _send(self, method, url, options):
                limit = options.pop("max_redirects", 20)
                for n in range(limit + 1):
                    if exclusions.skip(url):
                        raise ExcludedNavigation(url)
                    response = getattr(context, method)(url, max_redirects=0, **options)
                    location = response.headers.get("location")
                    if response.status not in (301, 302, 303, 307, 308) or not location or limit == 0:
                        return response
                    target = urljoin(response.url, location)
                    response.dispose()
                    if n == limit:
                        raise ValueError("리다이렉트 상한 초과")
                    url = target
                raise ValueError("리다이렉트 상한 초과")

            def get(self, url, **options):
                return self._send("get", url, options)

            def head(self, url, **options):
                return self._send("head", url, options)

            def post(self, url, **options):
                return self._send("post", url, options)

            def put(self, url, **options):
                return self._send("put", url, options)

            def patch(self, url, **options):
                return self._send("patch", url, options)

            def delete(self, url, **options):
                return self._send("delete", url, options)

            def fetch(self, url_or_request, **options):
                url = url_or_request if isinstance(url_or_request, str) else url_or_request.url
                return self._send("fetch", url, options)

            def __getattr__(self, name):
                # dispose()·storage_state() 등 조회가 아닌 기능은 그대로 넘긴다.
                return getattr(context, name)
        return Requests()
