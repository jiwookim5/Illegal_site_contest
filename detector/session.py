"""브라우저 세션: 페이지를 열고 판정해도 될 때까지 기다리는 방법, 지연 불러오기·'더보기', 열기 실패 사유.

전체 점검(scan)과 조치 확인(recheck)이 같은 세션을 써야 점검 때 잡힌 광고를 확인 때 놓치지 않는다.
"""
import re
import time

from scan_control import check_cancelled, wait, detail

from browser import NATIVE_HOOK, launch_browser, script_frames
from font_text import FontText
from canvas_text import CANVAS_HOOK

import js_links as js_mod
from politeness import USER_AGENT

# 판정에 쓰지 않는 글꼴·영상. 주소 끝으로 골라 이것만 가로채 막는다 (그림은 브라우저 설정으로 막는다)
HEAVY_URL = re.compile(r"\.(woff2?|ttf|otf|eot|mp4|webm|ogg|ogv|mp3|m4a|wav|avi|mov)(\?|#|$)", re.I)
AJAX_WAIT_MS = 2000     # 비동기로 불러오는 댓글 등을 기다리는 최대 시간
LAZY_WAIT_MS = 100      # 화면을 내린 뒤 지연 불러오기가 시작될 때까지 기다리는 시간

# 스크롤 좌표 변경만으로 IntersectionObserver 콜백이 실행된 것은 아니다.
# 다음 렌더링과 그 뒤 프레임까지 기다린다. 정지된 렌더러에서는 2초 뒤 반환한다.
WAIT_PAINT = """() => new Promise(resolve => {
  let first, second;
  const done = () => { clearTimeout(timer); cancelAnimationFrame(first);
                      cancelAnimationFrame(second); resolve(); };
  const timer = setTimeout(done, 2000);
  first = requestAnimationFrame(() => { second = requestAnimationFrame(done); });
})"""


def fail_reason(exc=None, status=None):
    """페이지를 못 연 까닭. (사유 코드, 다시 시도할 만한가).

    timeout·network·server·blocked 는 실패로 보고하고, gone(없는 주소)은 따로 센다.
    """
    if exc is not None:
        name, msg = type(exc).__name__, str(exc)
        if "Timeout" in name:
            return "timeout", True
        if "net::" in msg or "NS_ERROR" in msg:
            return "network", True
        return "error", False
    if status in (401, 403, 429):
        return "blocked", status == 429
    if status >= 500:
        return "server", True
    return "gone", False


def _dismiss_dialog(dialog):
    try:
        dialog.dismiss()
    except Exception:
        pass    # 알림을 띄운 창이 이미 닫혔다


def fail_entry(url, reason, status=None, detail=""):
    return {"url": url, "reason": reason, "status": status, "detail": detail[:200]}

# 모든 외부 스타일시트가 실제로 적용되었는지 확인한다.
STYLES_READY = """() => Array.from(document.querySelectorAll('link[rel~=\"stylesheet\"]'))
  .every(l => l.sheet || l.disabled)"""

# 페이지가 '화면을 내리면 더 불러오는' 장치를 쓰는지 표시해 둔다 (모든 페이지를 내려 보면 느리다).
# IntersectionObserver 를 만들거나 scroll 이벤트를 다는 페이지만 내려 본다.
LAZY_HOOK = r"""
(() => {
  // 페이지 스크립트보다 먼저 돌 때 잡아 둔다. 나중에 페이지가 Map 을 덮어써도 콜백 안에서 원래 것을 쓴다
  const Map = window.Map, WeakMap = window.WeakMap;
  const mark = () => { window.__hwonhiLazy = true; };
  const IO = window.IntersectionObserver;
  if (IO) {
    const Wrapped = function (cb, opt) { mark(); return new IO(cb, opt); };
    Wrapped.prototype = IO.prototype;
    window.IntersectionObserver = Wrapped;
  }
  // Initial short timers, their chained callbacks and intervals can insert text.
  // BrowserSession.open caps the total wait, including endlessly repeating timers.
  // Timers started by expansion actions are tracked with the same bounded policy.
  // Preserve closed mode while retaining a reference for inspection.
  const roots = new WeakMap(), attach = Element.prototype.attachShadow;
  Element.prototype.attachShadow = function (...args) {
    const root = attach.apply(this, args); roots.set(this, root); return root;
  };
  window.__hwonhiShadowRootOf = el => roots.get(el);
  const st = window.setTimeout, si = window.setInterval;
  const ct = window.clearTimeout, ci = window.clearInterval;
  // id -> { due, gen, decor, active }. gen tells which expansion action started the timer (0: page load),
  // so waiting after a click or scroll ignores rolling banners the page started at load.
  const pending = new Map();
  let inTrackedCallback = false, current = null;
  const DETACHED = {};
  const trackable = () => document.currentScript || !window.__hwonhiLoaded ||
                         window.__hwonhiTrack || inTrackedCallback;
  const dueSince = gen => {
    let due = 0;
    for (const e of pending.values()) if (e.gen >= gen) due = Math.max(due, e.due);
    return due;
  };
  Object.defineProperty(window, '__hwonhiDue', { get: () => dueSince(0) });
  Object.defineProperty(window, '__hwonhiReactDue', { get: () => dueSince(window.__hwonhiActionGen || 0) });
  window.addEventListener('load', () => st.call(window, () => { window.__hwonhiLoaded = true; }, 0));
  // A repeating timer (interval or setTimeout chain) whose ticks only change attributes (slide
  // classes, styles) is decoration: after DECOR_TICKS such ticks it no longer delays judgement.
  // A chain that has added no text for QUIET_MAX_MS of its life (analytics polling, scroll checks)
  // stops too. A chain that counts silently and inserts within that time (fourth tick at 1.6 s after
  // silent ticks up to 1.2 s) is still awaited, as is any single timer up to DELAY_MAX_MS.
  const DECOR_TICKS = 2, QUIET_MAX_MS = 1500;
  // A literal class toggle without stylesheets cannot hide existing content.
  // Observe its first tick, then stop waiting for the identical second tick.
  // CSS-driven toggles retain the full window, including their initial state.
  // Do not infer this from observed mutations:
  // a callback can change classes twice and insert advertising on a later tick.
  const classCycle = fn => {
    if (typeof fn !== 'function') return false;
    const src = Function.prototype.toString.call(fn).trim();
    const literal = "(?:'[^'\\\\\\r\\n]*'|\"[^\"\\\\\\r\\n]*\")";
    const call = 'document\\.getElementById\\(\\s*' + literal + '\\s*\\)\\.classList\\.toggle\\(\\s*' + literal + '\\s*\\)';
    return new RegExp('^(?:\\(\\s*\\)|[a-zA-Z_$][\\w$]*)\\s*=>\\s*(?:' + call + ';?|\\{\\s*' + call + ';?\\s*\\})$').test(src);
  };
  let mo = null;
  try {
    mo = new MutationObserver(() => {});
    mo.observe(document, { subtree: true, childList: true, characterData: true, attributes: true });
  } catch (e) { mo = null; }
  const textOf = n => (n.nodeType === 1 || n.nodeType === 3) ? (n.textContent || '').replace(/\s+/g, '') : '';
  const tickKind = recs => {
    if (!recs.length) return 'none';
    const added = new Map();
    for (const r of recs) {
      if (r.type === 'characterData') return 'text';
      if (r.type === 'attributes') continue;
      for (const n of r.addedNodes) { const t = textOf(n); if (t) added.set(t, (added.get(t) || 0) + 1); }
    }
    // Moving a slide re-adds a node whose text was removed in the same tick
    for (const r of recs) if (r.type === 'childList')
      for (const n of r.removedNodes) { const t = textOf(n); if (added.has(t)) added.set(t, added.get(t) - 1); }
    for (const c of added.values()) if (c > 0) return 'text';
    return 'decor';
  };
  const schedule = (native, interval) => function (fn, ms, ...rest) {
    const d = Math.max(interval ? 1 : 0, Number(ms) || 0);
    const parent = current && current !== DETACHED ? current : null;
    const tracked = current !== DETACHED && !!trackable() && d <= DELAY_MAX_MS;
    const entry = !tracked ? null : {
      due: performance.now() + d, active: true, kids: [],
      gen: parent ? parent.gen : (window.__hwonhiTrack ? (window.__hwonhiActionGen || 0) : 0),
      decor: parent ? parent.decor : 0,
      cycle: interval && classCycle(fn),
      quietSince: parent ? parent.quietSince : performance.now(),
    };
    let id;
    const wrapped = typeof fn !== 'function' ? fn : function (...args) {
      if (!interval) pending.delete(id);
      const live = !!entry && entry.active;
      const previous = inTrackedCallback, prevCurrent = current;
      inTrackedCallback = live;
      current = live ? entry : (entry ? DETACHED : prevCurrent === DETACHED ? DETACHED : null);
      if (live && mo) { mo.takeRecords(); entry.kids = []; }
      try { return fn.apply(this, args); }
      finally {
        inTrackedCallback = previous; current = prevCurrent;
        if (live) {
          const kind = mo ? tickKind(mo.takeRecords()) : 'text';
          const t = performance.now();
          if (kind === 'decor') entry.decor++;
          if (kind === 'text') { entry.decor = 0; entry.quietSince = t; }
          if (kind !== 'none' && entry.gen === 0) window.__hwonhiLate = true;
          const done = (entry.cycle && kind === 'decor' && !document.styleSheets.length &&
                        !document.adoptedStyleSheets.length) ||
            entry.decor >= DECOR_TICKS || (kind !== 'text' && t - entry.quietSince >= QUIET_MAX_MS);
          for (const k of entry.kids) {
            k.entry.decor = entry.decor; k.entry.quietSince = entry.quietSince;
            if (done) { k.entry.active = false; pending.delete(k.id); }
          }
          if (done) { entry.active = false; pending.delete(id); }
          else if (interval && pending.has(id)) entry.due = t + d;
        }
      }
    };
    id = native.call(this, wrapped, ms, ...rest);
    if (entry) {
      pending.set(id, entry);
      if (parent) parent.kids.push({ id, entry });
    }
    return id;
  };
  window.setTimeout = schedule(st, false);
  window.setInterval = schedule(si, true);
  window.clearTimeout = function (id) { pending.delete(id); return ct.call(this, id); };
  window.clearInterval = function (id) { pending.delete(id); return ci.call(this, id); };
  const add = EventTarget.prototype.addEventListener;
  EventTarget.prototype.addEventListener = function (type, ...rest) {
    if (type === 'scroll' || type === 'wheel') mark();
    return add.call(this, type, ...rest);
  };
})();
"""
DELAY_MAX_MS = 2000     # 이 안에 실행되도록 미뤄 둔 삽입만 기다린다
LOAD_WAIT_MS = 3000     # load 이벤트를 기다리는 최대 시간 (그림은 받지 않으므로 보통 바로 온다)
LAZY_HOOK = LAZY_HOOK.replace("DELAY_MAX_MS", str(DELAY_MAX_MS))

# 판정을 시작해도 되는지 한 번에 확인한다. load 이벤트(스타일시트·iframe 이 모두 붙은 시점)까지
# 기다리고, load 처리기가 끼워 넣은 글이 반영되도록 한 박자 쉰 뒤, 스타일 적용 여부와
# 미뤄 둔 삽입까지 남은 시간을 돌려준다. 예전처럼 모든 페이지에서 고정 시간을 쉬지 않는다.
PAGE_READY = """async () => {
  if (document.readyState !== 'complete')
    await new Promise((r) => { addEventListener('load', r, { once: true }); setTimeout(r, LOAD_WAIT_MS); });
  await new Promise((r) => setTimeout(r, 0));
  return { styles: (STYLES_READY)(), left: Math.max(0, (window.__hwonhiDue || 0) - performance.now()) };
}""".replace("LOAD_WAIT_MS", str(LOAD_WAIT_MS)).replace("STYLES_READY", STYLES_READY)
# iframe 안에서 미뤄 둔 삽입까지 남은 시간 (다른 출처 iframe 은 바깥 페이지에서 볼 수 없어 따로 묻는다)
DELAY_LEFT = "() => Math.max(0, (window.__hwonhiDue || 0) - performance.now())"
# 누르거나 내린 동작이 건 타이머만. 페이지가 열릴 때 건 넘기기 배너 타이머는 열 때 이미 기다렸다
REACT_LEFT = "() => Math.max(0, (window.__hwonhiReactDue || 0) - performance.now())"
# 판정을 시작한 뒤 페이지가 열릴 때 건 타이머가 화면을 바꿨는가 (바꿨으면 다시 판정한다)
LATE_RESET = "() => { window.__hwonhiLate = false; }"
LATE_READ = "() => !!window.__hwonhiLate"


def delay_left(page, left, js=DELAY_LEFT):
    """페이지(left: 페이지 자신의 남은 시간)와 그 안 iframe 들이 미뤄 둔 삽입 가운데
    가장 늦게 끝나는 것까지 남은 시간(ms)."""
    for fr in script_frames(page.frames[1:]):
        try:
            left = max(left, fr.evaluate(js))
        except Exception:
            pass
    return left


# 창 말고 글 상자 안(overflow:auto 인 댓글 상자 등)을 내려야 불러오는 경우도 있다
SCROLL_BOXES = """(go) => {
  let n = 0;
  for (const el of document.querySelectorAll('body *')) {
    if (n >= 20) break;
    if (el.scrollHeight <= el.clientHeight + 20) continue;
    const s = getComputedStyle(el).overflowY;
    if (s !== 'auto' && s !== 'scroll') continue;
    n++;
    if (go) el.scrollTop = el.scrollHeight;
  }
  return n;
}"""
LAZY_CHECK = ("() => !!window.__hwonhiLazy && (document.documentElement.scrollHeight > innerHeight + 50"
              " || (" + SCROLL_BOXES + ")(false) > 0)")
SCROLL_END = ("() => { window.scrollTo(0, document.documentElement.scrollHeight); (" + SCROLL_BOXES
              + ")(true); }")
SCROLL_TOP = "() => window.scrollTo(0, 0)"
REACT_MAX_MS = 2000     # 누르거나 내린 뒤 미뤄 둔 삽입·비동기 요청·iframe 을 기다리는 최대 시간
FRAME_WAIT_MS = 1500    # 그 사이 주소가 바뀐 iframe 이 다 열릴 때까지 기다리는 최대 시간


class Inflight:
    """진행 중인 비동기 요청. 요청마다 시작 순번을 적어, 누르거나 내린 뒤에는 그 뒤에 시작된 요청만 기다린다.

    페이지가 열릴 때부터 붙잡혀 있는 요청(실시간 알림·끝나지 않는 조회)을 동작마다 다시 기다리지 않는다.
    """

    def __init__(self):
        self._reqs, self._seq, self.since = {}, 0, 0

    def add(self, r):
        self._seq += 1
        self._reqs[r] = self._seq

    def discard(self, r):
        self._reqs.pop(r, None)

    def clear(self):
        self._reqs.clear()

    def __bool__(self):
        return bool(self._reqs)

    def __len__(self):
        return len(self._reqs)

    def mark(self):
        self.since = self._seq

    def recent(self):
        return _Recent(self)


class _Recent:
    def __init__(self, owner):
        self.owner = owner

    def __bool__(self):
        return any(seq > self.owner.since for seq in list(self.owner._reqs.values()))


def wait_reactions(page, inflight, settle_ms):
    """'더보기'·탭을 누르거나 화면을 내린 뒤, 그 동작이 불러오는 글이 다 붙을 때까지 기다린다.

    비동기 요청이 끝난 뒤 다시 타이머를 거는 경우(받아 와서 0.1초 뒤에 끼워 넣기)가 있어
    남은 타이머와 요청이 모두 없어질 때까지 되풀이한다. 끝나면 추적 표시를 끈다.
    """
    deadline = time.monotonic() + REACT_MAX_MS / 1000
    if hasattr(inflight, "recent"):
        inflight = inflight.recent()
    try:
        while time.monotonic() < deadline:
            check_cancelled()
            if inflight:
                _settle_ajax(page, inflight, settle_ms, deadline)
            left = delay_left(page, page.evaluate(REACT_LEFT), REACT_LEFT)
            if left <= 0 and not inflight:
                break
            remaining = max(0, (deadline - time.monotonic()) * 1000)
            step = min(int(left) + 20 if left > 0 else 50, remaining)
            wait(page, step)
        for fr in page.frames[1:]:
            check_cancelled()
            remaining = (deadline - time.monotonic()) * 1000
            if remaining <= 0:
                break
            try:
                fr.wait_for_load_state("load", timeout=min(FRAME_WAIT_MS, max(1, remaining)))
            except Exception:
                pass
    finally:
        try:
            page.evaluate(js_mod.TRACK_OFF)
        except Exception:
            pass


def _settle_ajax(page, inflight, settle_ms, deadline=None):
    """비동기 요청이 남아 있을 때만 끝날 때까지 기다린다 (없으면 지연 0)."""
    if not inflight:
        return
    deadline = min(deadline or float("inf"), time.monotonic() + AJAX_WAIT_MS / 1000)
    while inflight and time.monotonic() < deadline:
        wait(page, min(50, max(0, (deadline - time.monotonic()) * 1000)))
    wait(page, min(settle_ms, max(0, (deadline - time.monotonic()) * 1000)))


# 내려 볼 페이지인지와 '더보기' 후보를 한 번의 왕복으로 묻는다. 내려 봐야 하면 후보는 내린 뒤에 다시 찾는다.
EXPAND_PROBE = ("(limit) => { const lazy = (" + LAZY_CHECK + ")(); "
                "return { lazy, more: lazy ? null : (" + js_mod.MORE_CANDIDATES + ")(limit) }; }")


def reveal_lazy(page, inflight, settle_ms):
    """화면을 내려야 불러오는 댓글·목록을 불러온 뒤 맨 위로 돌아온다 (LAZY_CHECK 가 참인 페이지)."""
    js_mod.track_on(page)
    page.evaluate(SCROLL_END)
    page.evaluate(WAIT_PAINT)
    page.wait_for_timeout(LAZY_WAIT_MS)      # scroll 이벤트는 다음 화면 갱신 때 온다
    wait_reactions(page, inflight, settle_ms)
    page.evaluate(SCROLL_TOP)


class BrowserSession:
    """브라우저 하나와 그 위에서 페이지를 여는 방법. 전체 점검(scan)과 조치 확인(recheck)이 함께 쓴다.

    두 곳이 같은 대기·같은 '더보기' 처리를 거쳐야, 점검 때 잡힌 광고를 확인 때 놓치는 일이 없다.
    """

    def __init__(self, p, timeout_ms=20000, settle_ms=60):
        self.timeout_ms, self.settle_ms = timeout_ms, settle_ms
        self.browser, self.engine = launch_browser(p)
        # 정체를 밝히는 User-Agent 를 쓴다. 로그를 보는 담당자가
        # 정상 점검임을 알 수 있어야 관제에서 불필요한 대응을 하지 않는다.
        self.ctx = self.browser.new_context(ignore_https_errors=True, user_agent=USER_AGENT)
        self.ctx.add_init_script(NATIVE_HOOK)      # 페이지가 Map 등을 덮어쓰기 전에 원래 것을 잡아 둔다
        self.ctx.add_init_script(LAZY_HOOK)
        self.ctx.add_init_script(CANVAS_HOOK)
        # 알림창('로그인해 주세요')은 닫고 지나간다. 처리기가 없으면 Playwright 드라이버가 스스로 닫는데,
        # 알림을 띄운 창이 곧바로 닫히면 그 안에서 잡히지 않는 오류로 드라이버가 죽고 점검이 정체된다
        # (2026-10-20 광주교육청 누리집 304쪽째). 처리기 안의 오류는 여기서 잡을 수 있다
        self.ctx.on("dialog", _dismiss_dialog)
        self.font_text = FontText()
        # 판정에 CSS 는 반드시 필요하지만 이미지·폰트·영상은 쓰지 않는다.
        # 받지 않는 것만으로 페이지당 시간이 크게 줄고 대상 서버 부담도 준다.
        self.ctx.route(HEAVY_URL, lambda route: route.abort())
        # Later routes take precedence. Keep foreign fonts/media blocked.
        self.ctx.route(re.compile(r"\.(woff2?|ttf|otf)(\?|#|$)", re.I), self.font_text.route)
        # 자바스크립트 링크를 눌러 볼 때만 모든 요청을 가로채 페이지 이동과 GET 이 아닌 요청을 막는다.
        self.guard = js_mod.NavGuard(self.ctx)
        # 댓글처럼 페이지를 연 뒤 비동기로 불러오는 영역을 기다리기 위해 진행 중인 요청을 센다.
        self.inflight = Inflight()
        self.crashed = []
        self.probed = set()   # 이미 눌러 본 자바스크립트 링크의 생김새 (공통 메뉴를 페이지마다 다시 누르지 않게)
        self.navs = self._navs_at_watch = 0   # 탭 본문의 이동 횟수 (같은 주소로 다시 불러온 것도 센다)
        self.page = self._open_page()

    def _open_page(self):
        pg = self.ctx.new_page()
        pg._hwonhi_font_text = self.font_text
        pg._hwonhi_track_mark = self.inflight.mark
        pg.set_default_timeout(self.timeout_ms)
        pg.on("request", lambda r: self.inflight.add(r)
              if r.resource_type in ("xhr", "fetch") else None)
        pg.on("requestfinished", lambda r: self.inflight.discard(r))
        pg.on("requestfailed", lambda r: self.inflight.discard(r))
        pg.on("crash", lambda *_: self.crashed.append(True))
        pg.on("framenavigated", lambda f: self._count_nav(f))
        return pg

    def _count_nav(self, frame):
        if frame.parent_frame is None:
            self.navs += 1

    def settle(self):
        _settle_ajax(self.page, self.inflight, self.settle_ms)

    def open(self, url, defer_timers=False):
        """페이지를 열고 판정해도 될 때까지 기다린다. HTTP 상태 코드를 돌려준다 (접속 실패는 예외).

        defer_timers 이면 페이지가 미뤄 둔 삽입(타이머)을 여기서 기다리지 않는다. 부른 쪽은 판정 직전에
        watch_late(), 판정 뒤에 finish_timers() 를 불러, 기다리는 동안 펼치기·판정을 함께 한다.
        """
        self.timer_deadline, self.opened_url = None, None
        # 탭이 죽었으면(메모리 부족 등) 새 탭으로 이어 간다. 그대로 두면 남은 페이지가 모두 실패한다.
        if self.crashed or self.page.is_closed():
            try:
                self.page.close()
            except Exception:
                pass
            self.crashed.clear()
            self.inflight.clear()
            self.page = self._open_page()
        page = self.page
        # 앞 페이지에서 끝나지 않은 요청 기록은 이 페이지를 기다리는 데 쓰지 않는다
        self.inflight.clear()
        # 눌러 보다 열린 새 창을 닫으면 탭이 뒤로 밀린 것으로 여겨져 화면 갱신이 1초 안팎씩 늦어진다
        # (스크롤 뒤 화면 갱신 대기가 그만큼 늘어난다). 열기 전에 앞으로 가져온다
        try:
            page.bring_to_front()
        except Exception:
            pass
        check_cancelled()
        try:
            with detail("opening.response"):
                resp = page.goto(url, wait_until="domcontentloaded")
        except Exception:
            # 리다이렉트 순환 등으로 실패한 이동은 탭 안에서 오류 화면으로 이어지는 중일 수 있다.
            # 그 탭으로 다음 주소를 열면 남은 이동에 끼어들어("interrupted by another navigation")
            # 뒤의 페이지가 줄줄이 실패하고, 연속 실패로 점검이 멈춘다. 다음 주소는 새 탭으로 연다.
            self.crashed.append(True)
            raise
        check_cancelled()
        status = resp.status if resp is not None else 200
        if status >= 400:
            return status
        self._wait_ready(defer_timers)
        check_cancelled()
        with detail("opening.redirect"):
            page.wait_for_selector("body, frameset", state="attached", timeout=min(self.timeout_ms, 4000))
            redirect = page.evaluate("""() => {
              const m = document.querySelector('meta[http-equiv="refresh" i]');
              return m ? m.content : null;
            }""")
            if redirect and re.match(r"^\s*[0-5](?:\.\d+)?\s*;\s*url\s*=", redirect, re.I):
                before = page.url
                page.wait_for_url(lambda u: u != before, wait_until="domcontentloaded",
                                  timeout=min(self.timeout_ms, 6000))
        with detail("opening.ajax"):
            self.settle()
        if defer_timers:
            self.opened_url, self._navs_at_watch = page.url, self.navs
        return status

    def _wait_ready(self, defer_timers=False):
        # 스타일시트가 적용되기 전에 판정하면 display:none 같은 은닉을 통째로 놓친다.
        # load 까지 기다린 뒤에도 CSS 가 덜 붙었으면 더 기다리고, 페이지가 미뤄 둔
        # 삽입(setTimeout)이 남았으면 그때까지 기다린다 (defer_timers 이면 기한만 적어 둔다).
        page = self.page
        try:
            with detail("opening.load"):
                ready = page.evaluate(PAGE_READY)
            if not isinstance(ready, dict):
                raise RuntimeError("페이지 준비 상태를 읽지 못했습니다")
            if not ready["styles"]:
                with detail("opening.styles"):
                    page.wait_for_function(STYLES_READY, timeout=4000)
            deadline = time.monotonic() + DELAY_MAX_MS / 1000
            if defer_timers:
                self.timer_deadline = deadline
            else:
                self._wait_timers(deadline, delay_left(page, ready["left"]))
        except Exception:
            pass

    def _wait_timers(self, deadline, left=None, name="opening.timers"):
        page = self.page
        if left is None:
            left = delay_left(page, page.evaluate(DELAY_LEFT))
        while left > 0:
            remaining = (deadline - time.monotonic()) * 1000
            if remaining <= 0:
                break
            with detail(name):
                wait(page, min(left + 30, remaining))
            left = delay_left(page, page.evaluate(DELAY_LEFT))

    def watch_late(self):
        """판정 직전에 부른다. 이 뒤로 페이지가 열릴 때 건 타이머가 화면을 바꾸면 finish_timers 가 알려 준다."""
        for fr in script_frames(self.page.frames):
            try:
                fr.evaluate(LATE_RESET)
            except Exception:
                pass

    def finish_timers(self):
        """open(defer_timers=True) 에서 미룬 기다림을 마친다.

        None      판정한 화면 그대로다
        "changed" 판정 뒤에 타이머가 글이나 모양을 바꿨다. 다시 판정해야 한다
        "navigated" 타이머가 다른 주소로 넘기거나 같은 주소를 다시 불러왔다 (setTimeout 안의 location.href·reload).
                  넘어간 화면을 다 기다려 두었다
        """
        deadline, self.timer_deadline = self.timer_deadline, None
        opened, self.opened_url = self.opened_url, None
        page = self.page
        try:
            context_replaced = False
            if deadline:
                try:
                    self._wait_timers(deadline, name="analyze.late_timers")
                except Exception as exc:
                    if "Execution context was destroyed" not in str(exc):
                        raise
                    # A timer can reload between wait_for_timeout and evaluate.
                    # Continue through the navigation path instead of silently
                    # treating an empty result from the old document as final.
                    context_replaced = True
            if opened and (context_replaced or page.url.split("#")[0] != opened.split("#")[0] or
                           self.navs != self._navs_at_watch):
                page.wait_for_load_state("domcontentloaded", timeout=min(self.timeout_ms, 6000))
                self._wait_ready()
                self.settle()
                return "navigated"
            for fr in script_frames(page.frames):
                try:
                    if fr.evaluate(LATE_READ):
                        return "changed"
                except Exception:
                    pass
        except Exception:
            pass
        return None

    def expand(self):
        """화면을 내리거나 '더보기'를 눌러야 나오는 댓글을 불러온다."""
        try:
            probe = self.page.evaluate(EXPAND_PROBE, js_mod.MORE_LIMIT)
        except Exception:
            return
        check_cancelled()
        if not isinstance(probe, dict):
            raise RuntimeError("본문 확장 결과를 읽지 못했습니다")
        if probe["lazy"]:
            try:
                with detail("expand.scroll"):
                    reveal_lazy(self.page, self.inflight, self.settle_ms)
            except Exception:
                pass
        try:
            with detail("expand.more"):
                js_mod.expand_more(self.page, self.guard, self.react, first=probe["more"])
        except Exception:
            pass

    def react(self):
        wait_reactions(self.page, self.inflight, self.settle_ms)

    def switch_views(self, before=None, ids=None):
        """탭·'다음 페이지'처럼 같은 주소에서 화면을 바꾸는 단추를 하나씩 누른다.

        누를 때마다 멈추므로(yield) 부른 쪽이 바뀐 화면을 다시 훑는다. 바꾸면 앞 화면이 사라지므로
        처음 화면을 훑은 뒤에 불러야 한다. before 는 누를 단추가 있을 때 처음 누르기 전에 한 번 부른다.
        """
        yield from js_mod.switch_views(self.page, self.guard, self.react, before, ids)

    def close(self):
        try:
            self.browser.close()
        except Exception:
            pass
