"""자바스크립트로 이동하는 링크에서 갈 곳을 알아낸다.

공공 누리집 게시판(전자정부 표준프레임워크 등)은 글 목록을 <a href> 대신
href="javascript:fn_view('1024')", <tr onclick=...>, 스크립트가 붙인 클릭 이벤트,
fn_link_page(2) 같은 숨은 폼 전송으로 연결하는 경우가 많다. <a href> 만 따라가면
게시글에 한 건도 닿지 못한다.

1단계  코드 글자에서 주소를 읽는다 (location.href='...', window.open('...'), data-href 등)
2단계  그래도 모르면 눌러 본다. 이때 페이지 이동 요청은 주소만 기록하고 취소하며,
       GET 이 아닌 요청(삭제·등록 등)은 모두 막는다. 이름이 위험해 보이는 요소는 누르지 않는다.
3단계  fn_link_page(2) 처럼 숨은 폼을 POST 로 보내 여는 목록·게시글은, 보내려던 값을 GET 주소로
       바꿔 적는다 (전자정부 표준프레임워크 게시판 대부분이 pageIndex·nttId 를 GET 으로도 받는다).
       POST 는 여전히 서버에 보내지 않으며, 주소가 삭제·등록·저장처럼 보이면 바꾸지 않는다.
"""
import re
from scan_control import check_cancelled, count
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# 폼을 GET 주소로 바꿔 열어도 되는지: 처리(쓰기) 주소는 GET 으로도 동작할 수 있으니 열지 않는다
_RISKY_ACTION = re.compile(r"(delete|remove|insert|update|modify|write|regist|save|proc|login|logout|"
                           r"join|reply|comment|vote|recommend|upload|apply|submit|order|pay|cancel|"
                           r"삭제|등록|수정|저장)", re.I)
_RISKY_DEL = re.compile(r"(^|[/_.-])del([/_.-]|$)|del[A-Z]")


def post_as_get(action, fields):
    """POST 폼 전송을 같은 주소의 GET 요청으로 바꾼 주소. 열면 안 되는 주소면 None."""
    p = urlparse(action)
    if p.scheme not in ("http", "https") or _RISKY_ACTION.search(p.path) or _RISKY_DEL.search(p.path):
        return None
    q = dict(parse_qsl(p.query, keep_blank_values=True))
    for k, v in fields:
        q[k] = v                     # 폼 값이 주소에 이미 있는 값보다 우선한다
    return urlunparse(p._replace(query=urlencode(list(q.items()))))


# 페이지 안에서 후보를 모은다. 주소를 바로 읽을 수 있으면 urls 로, 눌러 봐야 하면 표시만 해 둔다.
# 공통 메뉴처럼 앞 페이지에서 이미 눌러 본 것과 생김새(HTML)가 똑같은 요소는 다시 누르지 않는다.
# 생김새는 짧은 해시(sig)로 주고받는다 (seen: 이미 눌러 본 해시들).
JS_CANDIDATES = r"""
([limit, seenList]) => {
  const seen = new Set(seenList || []);
  // 같은 생김새라도 다른 폴더(게시판)의 단추는 다른 곳으로 갈 수 있다 (상대 주소, 페이지마다 다른 리스너).
  // 폴더 경로를 함께 넣어, 공통 메뉴는 같은 폴더 안에서만 한 번 누른다.
  const dir = location.pathname.replace(/[^/]*$/, '');
  const sig = (el) => {
    const s = dir + el.outerHTML.slice(0, 600);
    let h = 5381;
    for (let i = 0; i < s.length; i++) h = ((h * 33) ^ s.charCodeAt(i)) | 0;
    return h;
  };
  const RISKY = /삭제|delete|remove|logout|log-out|로그아웃|탈퇴|수정|modify|update|edit|write|글쓰기|등록|저장|save|submit|추천|좋아요|like|신고|report|print|인쇄|스크랩|scrap|공유|share|닫기|close|history\.(back|go)|취소|cancel|reset|초기화|로그인|login|signin|장바구니|결제|신청하기|제출/i;
  // 코드에서는 submit 을 낱말로만 본다. 메뉴를 숨은 폼으로 여는 headerSubmit('/def/lawCase.do') 같은
  // 함수 이름까지 막으면 그런 누리집은 첫 화면에서 탐색이 끝난다 (lawcs.unilaw.go.kr: 메뉴 26개 중 25개).
  // 눌러도 이동은 취소되고 POST 는 보내지 않으며, 처리 주소는 GET 으로 바꾸지 않는다
  const RISKY_CODE = new RegExp(RISKY.source.replace('|submit|', '|\\bsubmit\\b|'), 'i');
  const URL_IN_CODE = /(?:location(?:\.href)?\s*=\s*|location\.(?:assign|replace)\(\s*|window\.open\(\s*|\bopen\(\s*)['"]([^'"]+)['"]/;
  const urls = [], probes = [], sigs = [];
  const add = (u) => { try { urls.push(new URL(u, location.href).href); } catch (e) {} };

  const cand = new Set(document.querySelectorAll(
    'a[href^="javascript:" i], a[href="#"], a[href=""], a:not([href])[onclick], [onclick], ' +
    '[data-href], [data-url], [data-link], [role="link"]'));
  // 스크립트가 addEventListener 로 붙인 클릭은 속성에 흔적이 없다. 손가락 커서가 시작되는 요소를 본다.
  // 폼 전송 단추는 아래에서 폼 값을 읽어 주소로 만든다
  for (const el of document.querySelectorAll('li, tr, td, div, span, img, p, dt, dd, article, section, ' +
                                             'button:not([type="submit"]), [role="button"]')) {
    if (cand.size > limit * 3) break;
    if (el.closest('a[href]:not([href^="javascript:" i]):not([href="#"])')) continue;
    const cur = getComputedStyle(el).cursor;
    if (cur === 'pointer' && (!el.parentElement || getComputedStyle(el.parentElement).cursor !== 'pointer'))
      cand.add(el);
  }

  let n = 0;
  for (const el of cand) {
    const href = el.getAttribute('href') || '';
    const code = (href.toLowerCase().startsWith('javascript:') ? href : '') + ' ' + (el.getAttribute('onclick') || '');
    // 게시글 제목("주민등록 안내")을 막지 않도록, 글자는 버튼처럼 짧을 때만 위험 여부를 본다
    const text = (el.textContent || '').trim();
    const names = (el.id || '') + ' ' + (typeof el.className === 'string' ? el.className : '') + ' ' +
                  (el.getAttribute('title') || '') + ' ' + (el.getAttribute('aria-label') || '');
    if (RISKY_CODE.test(code) || RISKY.test(names) || /(^|[\s_-])del([\s_-]|$)/i.test(names) ||
        (text.length <= 8 && RISKY.test(text))) continue;
    const direct = el.getAttribute('data-href') || el.getAttribute('data-url') || el.getAttribute('data-link');
    if (direct) { add(direct); continue; }
    const m = code.match(URL_IN_CODE);
    if (m) { add(m[1]); continue; }
    if (n >= limit) continue;
    const h = sig(el);
    if (seen.has(h)) continue;
    seen.add(h);
    el.setAttribute('data-hwonhi-probe', String(n));
    sigs.push(h);
    probes.push(n++);
  }
  // GET 폼(전자정부 상세보기·숨은 쪽 번호 폼 등)은 보낼 값을 읽어 주소로 만든다.
  // 글을 써 넣는 칸(검색어 등)이 있는 폼은 빈 검색 결과만 나오므로 보지 않는다.
  const forms = [];
  for (const f of document.forms) {
    if ((f.getAttribute('method') || 'get').toLowerCase() !== 'get') continue;
    if (RISKY.test((f.getAttribute('action') || '') + ' ' + (f.id || '') + ' ' + (f.className || ''))) continue;
    let typing = false, choice = null;
    const fields = [];
    for (const el of f.elements) {
      if (!el.name || el.disabled) continue;
      const t = (el.type || '').toLowerCase();
      if (['text', 'search', 'email', 'password', 'tel', 'number', 'textarea'].includes(t) && !el.readOnly) { typing = true; break; }
      if (['submit', 'button', 'reset', 'image', 'file'].includes(t)) continue;
      if ((t === 'checkbox' || t === 'radio') && !el.checked) continue;
      if (el.tagName === 'SELECT' && !choice) choice = [fields.length, el];
      fields.push([el.name, String(el.value)]);
    }
    if (typing || !fields.length) continue;
    forms.push([f.action, fields]);
    // '분야 선택 → 보기' 처럼 선택 상자로 고르는 GET 폼은 고를 수 있는 값마다 주소가 다르다 (첫 상자만, 몇 개까지만)
    if (choice) {
      let k = 0;
      for (const o of choice[1].options) {
        if (k >= limit) break;
        if (!o.value || o.value === choice[1].value || o.disabled) continue;
        const alt = fields.map((x) => x.slice());
        alt[choice[0]][1] = o.value;
        forms.push([f.action, alt]);
        k++;
      }
    }
  }
  // <select onchange="location.href=this.value"> 처럼 고르면 이동하는 목록: 값이 주소인 항목
  const URLISH = /^(https?:\/\/|\/|\.{1,2}\/)\S*$|^[\w.-]+\.(html?|do|jsp|php|aspx?)(\?\S*)?$/i;
  let opts = 0;
  for (const o of document.querySelectorAll('select option')) {
    if (opts >= limit) break;
    const v = (o.getAttribute('value') || '').trim();
    if (v && URLISH.test(v) && !RISKY.test(v)) { add(v); opts++; }
  }
  return { urls, probes, sigs, forms };
}
"""

PROBE_LIMIT = 60        # 한 페이지에서 눌러 볼 최대 요소 수
AFTER_CLICK_MS = 40     # 이동 요청이 나올 때까지 기다리는 시간
# 눌러 본 뒤 페이지를 다시 열지 않으므로, 앞서 누른 단추(기간·분야 선택 등)가 바꾼 폼 값을 누르기 전에 되돌린다.
# 되돌리지 않으면 뒤의 쪽 번호 단추가 바뀐 조건으로 주소를 만들어 실제 목록 쪽을 놓친다
FORMS_SAVE = ("() => { window.__hwonhiForms = Array.from(document.querySelectorAll('input, select, textarea'))"
              ".map(el => [el, el.value, el.checked, el.selectedIndex]); }")
_RESTORE_FORMS = r"""
  for (const [el, value, checked, index] of (window.__hwonhiForms || [])) {
    try {
      if (el.tagName === 'SELECT') el.selectedIndex = index;
      else { if (el.type !== 'file' && el.value !== value) el.value = value; el.checked = checked; }
    } catch (e) {}
  }"""
CLICK_JS = r"""(i) => {""" + _RESTORE_FORMS + r"""
  const e = document.querySelector(`[data-hwonhi-probe="${i}"]`); if (e) e.click();
}"""
# 후보를 한 번에 차례로 누른다. 누를 때마다 폼 값을 되돌리는 것은 하나씩 누를 때와 같다.
# form.submit() 의 이동은 누른 그 순간이 아니라 다음 작업으로 미뤄지고, 미뤄진 전송은 뒤의 전송이
# 덮어쓴다 ('2쪽' 다음 바로 '3쪽'을 누르면 2쪽 주소가 사라진다). 그래서 누를 때마다 한 번 양보해
# 미뤄진 이동이 먼저 걸리게 한다.
# 주소가 바뀌면(취소되지 않은 이동·pushState) 거기서 멈춘다. 파이썬 쪽이 하나씩 누르기로 다시 한다
BATCH_CLICK = r"""async (ids) => {
  const start = location.href.split('#')[0];
  const later = (window.__hwonhiNative || window).setTimeout;
  for (const i of ids) {""" + _RESTORE_FORMS + r"""
    const e = document.querySelector(`[data-hwonhi-probe="${i}"]`); if (e) e.click();
    await new Promise(r => later(r, 0));
    if (location.href.split('#')[0] !== start) break;
  }
}"""
# 한 번에 누른 뒤 늦게 걸리는 이동(setTimeout 안의 location 변경)까지 기다리는 시간.
# 하나씩 누를 때는 요소마다 AFTER_CLICK_MS 를 기다렸다
BATCH_WAIT_MS = 150

# 페이지 안에서 이동을 막고 목적지만 적어 둔다. 네트워크에서 끊으면 브라우저가 오류 페이지로
# 넘어가 남은 요소를 누를 수 없으므로, Navigation API 로 이동 자체를 취소한다.
# POST 폼 전송(formData 있음)은 보내려던 값과 주소를 따로 적어 두고, 파이썬에서 GET 주소로 바꾼다.
# window.open 은 주소만 적는다.
INSTALL_TRAP = r"""
() => {
  window.__hwonhiNav = [];
  window.__hwonhiPost = [];
  if (window.__hwonhiTrap) return;
  window.__hwonhiTrap = true;
  if (window.navigation) {
    navigation.addEventListener('navigate', (e) => {
      if (!e.formData) window.__hwonhiNav.push(e.destination.url);
      else {
        const fields = [];
        let file = false;
        for (const [k, v] of e.formData) { if (typeof v === 'string') fields.push([k, v]); else file = true; }
        if (!file) window.__hwonhiPost.push([e.destination.url, fields]);
      }
      if (e.cancelable) e.preventDefault();
    });
  }
  window.open = function (u) {
    if (u) { try { window.__hwonhiNav.push(new URL(u, location.href).href); } catch (e) {} }
    return null;
  };
}
"""
READ_TRAP = "() => window.__hwonhiNav || []"
READ_POST = "() => window.__hwonhiPost || []"


# '댓글 더보기'가 보내는 POST 가운데 조회로 보이는 것만 허용한다 (전자정부 게시판의 selectCmtList.do 등).
# 주소에 조회 낱말이 있고 쓰기 낱말이 없어야 한다. 쓰기 낱말이 하나라도 있으면 조회 낱말이 있어도 막는다.
_READ_POST = re.compile(r"(list|select|get|search|retrieve|inquir|more|load|view|read|page|paging|fetch|"
                        r"lookup|목록|조회)", re.I)
_WRITE_POST = re.compile(r"(delete|remove|insert|update|modify|write|regist|save|proc|login|logout|join|vote|"
                         r"recommend|upload|apply|submit|order|pay|cancel|create|edit|report|like|"
                         r"삭제|등록|수정|저장|신고|추천)", re.I)


_DEL_CAMEL = re.compile(r"Del(?![a-z])")      # selectListDel.do, cmtDel.do (Delivery 는 제외)


def is_read_post(url):
    """비동기 POST 가 댓글·목록을 읽어 오는 요청으로 보이는가."""
    path = urlparse(url).path
    return (bool(_READ_POST.search(path)) and not _WRITE_POST.search(path)
            and not _RISKY_DEL.search(path) and not _DEL_CAMEL.search(path))


class NavGuard:
    """눌러 보는 동안 페이지 이동을 가로채 주소만 남기고, GET 이 아닌 요청은 막는다.

    probing 을 켜는 동안에만 컨텍스트의 모든 요청을 가로챈다. 가로채기는 요청마다 프로그램과
    왕복이 생겨(요청 하나에 수 ms) 평소에도 걸어 두면 CSS·스크립트가 많은 페이지가 크게 느려진다.
    """

    def __init__(self, ctx=None):
        self._ctx = ctx
        self._probing = False
        self.read_post = False      # '더보기'를 누르는 동안: 조회로 보이는 비동기 POST 는 보낸다
        self.allowed_posts = []     # 그렇게 허용한 POST 주소 (기록용)
        self.found = []
        self.posts = []             # 막은 POST 이동의 (주소, 폼 값). GET 주소로 바꿔 볼 후보

    @property
    def probing(self):
        return self._probing

    @probing.setter
    def probing(self, on):
        if on == self._probing:
            return
        self._probing = on
        if self._ctx is None:
            return
        try:
            if on:
                self._ctx.route("**/*", self._route)
            else:
                self._ctx.unroute("**/*", self._route)
        except Exception:
            pass

    def _route(self, route):
        if not self.handle(route):
            route.fallback()           # 글꼴·영상을 막는 처리기 등 앞서 건 처리로 넘긴다

    def handle(self, route):
        """가로챘으면 True. 아니면 False 를 돌려 원래 처리로 넘긴다."""
        if not self.probing:
            return False
        req = route.request
        # '댓글 더보기'가 iframe 주소를 바꿔 댓글을 띄우는 경우가 있다. iframe 안의 GET 이동은
        # 페이지를 떠나지 않으므로 그대로 보낸다
        if req.is_navigation_request() and req.method == "GET":
            try:
                if req.frame.parent_frame is not None:
                    return False
            except Exception:
                pass
        if req.is_navigation_request():
            if req.method == "GET":
                self.found.append(req.url)
            elif req.method == "POST":
                ctype = (req.headers.get("content-type") or "").lower()
                if "application/x-www-form-urlencoded" in ctype:
                    try:
                        self.posts.append((req.url, parse_qsl(req.post_data or "",
                                                              keep_blank_values=True)))
                    except Exception:
                        pass
            # 'aborted' 로 끊으면 브라우저가 오류 화면으로 넘어가지 않고 지금 문서에 머문다.
            # 그래서 눌러 볼 때마다 페이지를 다시 열 필요가 없다. POST 는 서버에 보내지 않는다
            route.abort("aborted")
            return True
        if (req.method == "POST" and self.read_post and req.resource_type in ("xhr", "fetch")
                and is_read_post(req.url)):
            self.allowed_posts.append(req.url)
            return False
        if req.method not in ("GET", "HEAD"):
            route.abort()              # 삭제·등록 같은 요청은 서버에 닿지 않는다
            return True
        return False


def discover(page, ctx, guard, seen=None, data=None):
    """이 페이지에서 자바스크립트로 갈 수 있는 주소들.

    seen 은 한 번의 점검 동안 이어지는 집합으로, 이미 눌러 본 요소의 생김새 해시를 담는다.
    data 는 이미 구해 둔 JS_CANDIDATES 결과다 (없으면 여기서 구한다).
    """
    seen = set() if seen is None else seen
    if data is None:
        try:
            data = page.evaluate(JS_CANDIDATES, [PROBE_LIMIT, list(seen)])
        except Exception:
            return []
    urls = list(data.get("urls", []))
    for action, fields in data.get("forms", []):
        u = post_as_get(action, fields)       # 처리(쓰기)처럼 보이는 주소는 None
        if u:
            urls.append(u)
    probes = data.get("probes", [])
    seen.update(data.get("sigs", []))
    if not probes:
        return urls

    popups = []

    def on_page(p):             # Playwright 는 내장 메서드를 처리기로 받지 못한다
        popups.append(p)

    ctx.on("page", on_page)
    start_url = page.url
    guard.probing, guard.found, guard.posts = True, [], []
    posts = []
    def same_page():
        return page.url.split("#")[0] == start_url.split("#")[0]

    def reopen():
        """원래 페이지로 돌아가 같은 순서로 다시 표시한다. 실패하면 False."""
        count("discover.reload")
        guard.probing = False
        try:
            page.goto(start_url, wait_until="domcontentloaded")
            # 같은 순서로 다시 표시한다 (방금 등록한 해시는 빼고 넘겨야 같은 요소에 같은 번호가 붙는다)
            page.evaluate(JS_CANDIDATES, [PROBE_LIMIT, list(seen.difference(data.get("sigs", [])))])
            page.evaluate(INSTALL_TRAP)
            page.evaluate(FORMS_SAVE)
            return True
        except Exception:
            return False
        finally:
            guard.probing = True

    try:
        page.evaluate(INSTALL_TRAP)
        page.evaluate(FORMS_SAVE)
        count("discover.probes", len(probes))
        # 먼저 후보 전부를 한 번에 누른다. 이동은 페이지 안에서 취소되고 목적지만 적히므로(INSTALL_TRAP)
        # 대부분의 페이지는 브라우저 왕복 한 번과 대기 한 번으로 끝난다.
        # 막지 못한 이동으로 페이지가 바뀌면 그 페이지만 아래의 하나씩 누르기로 처음부터 다시 한다
        rest = probes
        try:
            page.evaluate(BATCH_CLICK, probes)
            page.wait_for_timeout(BATCH_WAIT_MS)
            if same_page():
                urls += page.evaluate(READ_TRAP)
                posts += page.evaluate(READ_POST)
                rest = []
                count("discover.batch")
        except Exception:
            pass
        if rest:
            count("discover.fallback")
            if not same_page():
                if page.url.startswith(("http://", "https://")):
                    urls.append(page.url)
                if not reopen():
                    rest = []
            else:
                try:
                    urls += page.evaluate(READ_TRAP)
                    posts += page.evaluate(READ_POST)
                    page.evaluate(INSTALL_TRAP)
                except Exception:
                    pass
        for i in rest:
            check_cancelled()
            # Playwright 의 click 은 취소된 이동을 '진행 중'으로 여겨 다음 클릭을 기다리게 하므로
            # 페이지 안에서 직접 누른다 (onclick·javascript: 링크·addEventListener 모두 동작)
            try:
                page.evaluate(CLICK_JS, i)
            except Exception:
                continue
            page.wait_for_timeout(AFTER_CLICK_MS)
            # 페이지 안에서 취소되지 않은 이동(예: form.submit())은 네트워크에서 'aborted' 로 끊겨
            # 지금 문서에 그대로 머문다. 주소가 그대로면 다시 열지 않고 다음 요소를 누른다
            if same_page():
                continue
            # 막지 못한 이동(오류 페이지로 넘어감) 또는 history.pushState 로 주소만 바꾼 화면.
            # 주소를 적고 원래 페이지로 돌아가 같은 순서로 다시 표시한 뒤 이어서 누른다.
            urls.append(page.url)
            try:
                urls += page.evaluate(READ_TRAP)
                posts += page.evaluate(READ_POST)
            except Exception:
                pass
            if not reopen():
                break
        try:
            urls += page.evaluate(READ_TRAP)
            posts += page.evaluate(READ_POST)
        except Exception:
            pass
    finally:
        guard.probing = False
        ctx.remove_listener("page", on_page)
        for p in popups:
            try:
                p.close()
            except Exception:
                pass
        if popups:
            try:
                page.bring_to_front()       # 닫은 창 때문에 뒤로 밀린 탭은 화면 갱신이 늦어진다
            except Exception:
                pass
    for action, fields in posts + guard.posts:
        u = post_as_get(action, fields)
        if u:
            urls.append(u)
    return urls + guard.found


# '더보기'·탭처럼 같은 페이지에서 눌러 보는 단추 가운데 누르면 안 되는 것 (MORE·SWITCH 가 같이 쓴다)
_CLICK_RISKY = ("const RISKY = /삭제|delete|remove|logout|로그아웃|탈퇴|수정|modify|write|글쓰기|등록|저장|save|"
                "신고|report|추천|좋아요|like/i;")


# 댓글 '더보기'·'이전 댓글'처럼 누르면 같은 페이지에 글을 더 불러오는 단추.
# 실제 주소로 이동하는 링크(<a href="/list?page=2">더보기</a>)는 크롤링이 따라가므로 누르지 않는다.
MORE_CANDIDATES = r"""
(limit) => {
  const MORE = /^(댓글\s*|답글\s*|의견\s*)?(더\s*보기|more|load\s*more|이전\s*댓글(\s*보기)?|(댓글|답글)\s*(전체\s*)?보기|(댓글|답글)\s*\d+\s*개?\s*(모두\s*)?보기)[\s+▼▽∨⌄()\d]*$/i;
  CLICK_RISKY
  // 거의 모든 페이지에는 '더보기' 단추가 없다. 낱말이 아예 없으면 요소마다 글자를 읽지 않고 끝낸다
  const body = document.body ? document.body.textContent : '';
  if (!/더\s*보기|more|댓글|답글/i.test(body) && !document.querySelector(
      '[aria-label*="더보기"], [aria-label*="댓글"], [aria-label*="more" i], [title*="더보기"], [title*="댓글"]'))
    return [];
  const out = [];
  // 앞 회차에 누른 단추도 표시가 남아 있으므로 번호를 이어서 붙인다 (0 부터 다시 붙이면 옛 단추를 또 누른다)
  const base = document.querySelectorAll('[data-hwonhi-more]').length;
  for (const el of document.querySelectorAll('summary, button, a, [role="button"], [onclick], span, div, p, li, em, strong')) {
    if (out.length >= limit) break;
    if (el.hasAttribute('data-hwonhi-more') || el.disabled) continue;
    // Native comment disclosures are read before classifying their contents.
    // Never toggle an already open disclosure or click a nested label twice.
    const disclosure = el.closest('summary');
    if (disclosure && disclosure !== el) continue;
    if (disclosure && (el.parentElement?.tagName !== 'DETAILS' || el.parentElement.open ||
        el.parentElement.querySelector('summary') !== el || el.querySelector('a,button,input,select,textarea'))) continue;
    const link = el.closest('a[href]');
    if (link) {
      const h = (link.getAttribute('href') || '').trim();
      if (h && h !== '#' && !/^javascript:/i.test(h)) continue;
    }
    const t = (el.textContent || '').replace(/\s+/g, ' ').trim();
    // 글자는 '댓글' 뿐이고 '댓글 더보기'는 aria-label 에만 적은 단추도 있다
    const label = (el.getAttribute('aria-label') || el.getAttribute('title') || '').replace(/\s+/g, ' ').trim();
    const ok = (s) => s && s.length <= 20 && (MORE.test(s) || (disclosure && /^(댓글|답글|의견)\s*펼치기[\s▼▽∨⌄]*$/.test(s)));
    if (!t || !(ok(t) || ok(label))) continue;
    // 글자를 가진 가장 안쪽 요소 하나만 누른다 (단추와 그 안의 span 을 두 번 누르지 않게)
    if (!disclosure && Array.from(el.children).some((c) => (c.textContent || '').replace(/\s+/g, ' ').trim() === t)) continue;
    if (!el.getClientRects().length) continue;            // 보이지 않는 단추
    const names = (el.id || '') + ' ' + (typeof el.className === 'string' ? el.className : '') + ' ' +
                  (el.getAttribute('onclick') || '') + ' ' + ((link && link.getAttribute('href')) || '');
    if (RISKY.test(names)) continue;
    const id = base + out.length;
    el.setAttribute('data-hwonhi-more', String(id));
    out.push(id);
  }
  return out;
}
""".replace("CLICK_RISKY", _CLICK_RISKY)
MORE_CLICK = "(i) => { const e = document.querySelector(`[data-hwonhi-more=\"${i}\"]`); if (e) e.click(); }"
# 누른 뒤 페이지가 setTimeout 으로 미뤄 둔 삽입을 세도록 한다 (session.LAZY_HOOK 이 이 표시를 본다)
# 동작마다 번호(__hwonhiActionGen)를 올려, 기다릴 때 이 동작 뒤에 걸린 타이머만 센다
TRACK_ON = ("() => { window.__hwonhiTrack = true;"
            " window.__hwonhiActionGen = (window.__hwonhiActionGen || 0) + 1; }")
TRACK_OFF = "() => { window.__hwonhiTrack = false; }"


def track_on(page):
    """누르거나 내리기 직전에 부른다. 세션이 이 시점 뒤에 시작된 비동기 요청만 기다리도록 표시한다."""
    page.evaluate(TRACK_ON)
    mark = getattr(page, "_hwonhi_track_mark", None)
    if mark:
        mark()
MORE_ROUNDS = 3          # 누른 뒤 새 '더보기'가 또 나오면 이만큼 더 누른다
MORE_LIMIT = 5           # 한 번에 누를 단추 수


def _press(page, guard, settle, click_js, ids):
    """같은 페이지에서 단추들을 누르고 불러오기가 끝날 때까지 기다린다 ('더보기'·탭이 같이 쓴다).

    누르는 동안은 페이지 이동을 취소하고, 조회로 보이는 비동기 POST 말고는 GET 이 아닌 요청을 막는다.
    """
    guard.probing, guard.found, guard.posts = True, [], []
    guard.read_post = True
    try:
        page.evaluate(INSTALL_TRAP)
        track_on(page)
        for i in ids:
            check_cancelled()
            page.evaluate(click_js, i)
        page.wait_for_timeout(AFTER_CLICK_MS)
        settle()
    finally:
        guard.probing = guard.read_post = False


def expand_more(page, guard, settle, first=None):
    """'댓글 더보기' 같은 단추를 눌러 같은 페이지에 글을 더 불러온다.

    누르는 동안에는 눌러 보기(discover)와 같이 페이지 이동을 취소하고 GET 이 아닌 요청을 막는다.
    다만 전자정부 게시판처럼 댓글 목록을 비동기 POST(selectCmtList.do 등)로 불러오는 경우가 많아,
    주소가 조회로 보이고 쓰기 낱말(delete·insert·save 등)이 없는 비동기 POST 만은 보낸다.
    페이지 이동·폼 전송 POST 는 여전히 보내지 않는다. settle 은 불러오기가 끝날 때까지 기다리는 함수다.
    first 는 이미 찾아 둔 첫 회차 후보다 (없으면 None, 이때는 여기서 찾는다).
    """
    start = page.url
    clicked = 0
    for n in range(MORE_ROUNDS):
        ids = first if n == 0 and first is not None else page.evaluate(MORE_CANDIDATES, MORE_LIMIT)
        if not ids:
            break
        _press(page, guard, settle, MORE_CLICK, ids)
        clicked += len(ids)
        if page.url.split("#")[0] != start.split("#")[0]:
            page.goto(start, wait_until="domcontentloaded")
            break
    return clicked


# 같은 주소에서 화면을 바꾸는 단추: 고르지 않은 탭, 주소 없이 목록을 갈아 끼우는 '다음 페이지'.
# '더보기'와 달리 앞 화면이 사라지므로 한 번에 하나씩 누르고, 누를 때마다 화면을 다시 훑는다.
SWITCH_CANDIDATES = r"""
(limit) => {
  const NEXT = /^(다음(\s*페이지)?|next(\s*page)?)$/i;
  const ARROWS = /[\s▶▷►›»>→]+/g;
  CLICK_RISKY
  const base = document.querySelectorAll('[data-hwonhi-switch]').length;
  const out = [];
  for (const el of document.querySelectorAll('[role="tab"], button, a, [role="button"]')) {
    if (out.length >= limit) break;
    if (el.hasAttribute('data-hwonhi-switch') || el.disabled || !el.getClientRects().length) continue;
    const link = el.closest('a[href]');
    if (link) {
      const h = (link.getAttribute('href') || '').trim();
      if (h && h !== '#' && !/^javascript:/i.test(h)) continue;     // 진짜 주소는 크롤링이 따라간다
    }
    if (el.closest('form') && (el.type || '').toLowerCase() === 'submit') continue;
    const tab = el.getAttribute('role') === 'tab' && el.getAttribute('aria-selected') === 'false';
    const words = [(el.textContent || ''), (el.getAttribute('aria-label') || '')]
      .map((s) => s.replace(ARROWS, ' ').replace(/\s+/g, ' ').trim());
    if (!tab && !words.some((s) => s && NEXT.test(s))) continue;
    const names = (el.id || '') + ' ' + (typeof el.className === 'string' ? el.className : '') + ' ' +
                  (el.getAttribute('onclick') || '') + ' ' + ((link && link.getAttribute('href')) || '');
    if (RISKY.test(names)) continue;
    const id = base + out.length;
    el.setAttribute('data-hwonhi-switch', String(id));
    out.push(id);
  }
  return out;
}
""".replace("CLICK_RISKY", _CLICK_RISKY)
SWITCH_CLICK = "(i) => { const e = document.querySelector(`[data-hwonhi-switch=\"${i}\"]`); if (e) e.click(); }"
SWITCH_LIMIT = 3         # 한 페이지에서 바꿔 볼 화면 수


def switch_views(page, guard, settle, before=None, ids=None):
    """화면을 바꾸는 단추를 하나씩 누르고, 누를 때마다 멈춘다(yield). 부른 쪽은 그때 화면을 다시 훑는다.

    누르는 동안은 '더보기'와 같이 페이지 이동을 취소하고 쓰기 요청을 막는다. 그래도 주소가 바뀌면
    (이동하는 단추였으면) 원래 페이지로 돌아가 멈춘다. 이동할 주소는 눌러 보기(discover)가 따로 모은다.
    before 는 누를 단추가 있을 때만, 처음 누르기 전에 한 번 부른다 (바꾸기 전 화면 기록).
    ids 는 이미 표시해 둔 SWITCH_CANDIDATES 결과다 (없으면 여기서 찾는다).
    """
    if ids is None:
        try:
            ids = page.evaluate(SWITCH_CANDIDATES, SWITCH_LIMIT)
        except Exception:
            return
    if ids and before is not None:
        before()
    start = page.url
    for i in ids:
        check_cancelled()
        try:
            _press(page, guard, settle, SWITCH_CLICK, [i])
        except Exception:
            return
        if page.url.split("#")[0] != start.split("#")[0]:
            try:
                page.goto(start, wait_until="domcontentloaded")
            except Exception:
                pass
            return
        yield i


# 자바스크립트로 내려받는 첨부(전자정부 표준 fn_egov_downFile('FILE_...','0'), onclick="fileDown(..)",
# 숨은 폼 전송 등). <a href> 가 아니라서 첨부 검사기가 받는 링크 목록에 들지 않는다.
# 내려받기처럼 보이는 요소만 골라 눌러 보고, 잡힌 주소를 그 요소의 위치와 함께 돌려준다.
DOWNLOAD_CANDIDATES = r"""
(limit) => {
  BUILD_SELECTOR
  const HINT = /down|file|atch|attach|첨부|다운|내려받|\.(pdf|hwpx?)\b/i;
  const RISKY = /삭제|delete|remove|upload|올리기|수정|modify|update|등록|저장|save|submit|logout|로그아웃|del(?![a-z])/i;
  const out = [];
  for (const el of document.querySelectorAll(
      'a[href^="javascript:" i], a[href="#"], a[href=""], a:not([href])[onclick], [onclick]')) {
    if (out.length >= limit) break;
    if (el.closest('[data-hwonhi-dl]')) continue;          // 바깥 요소를 이미 골랐으면 안쪽은 두 번 누르지 않는다
    const href = el.getAttribute('href') || '';
    const code = (href.toLowerCase().startsWith('javascript:') ? href : '') + ' ' + (el.getAttribute('onclick') || '');
    const text = (el.textContent || '').replace(/\s+/g, ' ').trim().slice(0, 200);
    const names = (el.id || '') + ' ' + (typeof el.className === 'string' ? el.className : '') + ' ' +
                  (el.getAttribute('title') || '');
    if (RISKY.test(code) || RISKY.test(names) || (text.length <= 8 && RISKY.test(text))) continue;
    if (!HINT.test(code) && !HINT.test(text) && !HINT.test(names)) continue;
    el.setAttribute('data-hwonhi-dl', String(out.length));
    out.push({ i: out.length, selector: buildSelector(el), text });
  }
  return out;
}
"""
DOWNLOAD_CLICK = "(i) => { const e = document.querySelector(`[data-hwonhi-dl=\"${i}\"]`); if (e) e.click(); }"
DOWNLOAD_LIMIT = 20      # 한 페이지에서 눌러 볼 첨부 단추 수


def download_links(page, guard, limit=DOWNLOAD_LIMIT):
    """자바스크립트로 내려받는 첨부의 [{selector, href, text}].

    눌러 보는 동안은 discover() 와 같이 페이지 이동을 취소해 주소만 적고, GET 이 아닌 요청은 막는다.
    숨은 폼을 POST 로 보내 내려받는 경우는 같은 값을 GET 주소로 바꿔 적는다 (post_as_get).
    """
    from selector_js import BUILD_SELECTOR
    cands = page.evaluate(DOWNLOAD_CANDIDATES.replace("BUILD_SELECTOR", BUILD_SELECTOR.strip(), 1), limit)
    if not cands:
        return []
    start = page.url
    out = []
    guard.probing, guard.found, guard.posts = True, [], []
    try:
        page.evaluate(INSTALL_TRAP)
        for c in cands:
            n_nav, n_post = len(page.evaluate(READ_TRAP)), len(page.evaluate(READ_POST))
            n_found, n_gposts = len(guard.found), len(guard.posts)
            try:
                page.evaluate(DOWNLOAD_CLICK, c["i"])
            except Exception:
                continue
            page.wait_for_timeout(AFTER_CLICK_MS)
            if page.url.split("#")[0] != start.split("#")[0]:
                break                    # 막지 못한 이동. 이 페이지에서는 더 누르지 않는다
            urls = page.evaluate(READ_TRAP)[n_nav:] + guard.found[n_found:]
            for action, fields in page.evaluate(READ_POST)[n_post:] + guard.posts[n_gposts:]:
                u = post_as_get(action, fields)
                if u:
                    urls.append(u)
            for u in dict.fromkeys(urls):
                out.append({"selector": c["selector"], "href": u, "text": c["text"]})
    finally:
        guard.probing = False
    if page.url.split("#")[0] != start.split("#")[0]:
        page.goto(start, wait_until="domcontentloaded")
    return out
