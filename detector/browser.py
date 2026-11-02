"""브라우저 실행 경로를 한곳에서 정한다.

Windows 10/11 에 기본 탑재된 Edge 로 탐지한다. 브라우저를 동봉하지 않아
배포본이 작고, 서명 없는 대용량 실행 파일이 늘어나지 않는다.
"""
import json

# 판정에 그림은 쓰지 않는다. 요청을 가로채 막으면 요청마다 프로그램과 왕복이 생겨 느리므로
# 브라우저 설정으로 아예 받지 않는다 (CSS 바탕 그림 포함)
LAUNCH_ARGS = ["--disable-dev-shm-usage", "--disable-gpu", "--blink-settings=imagesEnabled=false"]
CHANNEL = "msedge"


def pdf_viewer_frame(frame):
    """브라우저가 PDF 문서 안에 만든 뷰어 프레임인가.

    iframe 이 PDF 를 바로 띄우면(교육부 업무계획 페이지) 브라우저가 그 아래에 about:blank 프레임을
    하나 만든다. 이 프레임은 스크립트 실행에 답하지 않아, 시간 제한이 없는 evaluate 가 끝나지 않고
    점검 전체가 '정체'로 멈췄다. 이름(32자리 16진수)만 보면 광고를 숨긴 iframe 이 흉내 낼 수 있으므로
    부모 문서가 실제로 PDF 인지 본다 (PDF 문서는 다른 HTML 프레임을 품을 수 없다).
    """
    parent = frame.parent_frame
    if parent is None or frame.url != "about:blank":
        return False
    try:
        return parent.evaluate("() => document.contentType") == "application/pdf"
    except Exception:
        return False


def script_frames(frames):
    """스크립트를 실행할 수 있는 프레임만 (PDF 뷰어 프레임을 뺀다)."""
    return [fr for fr in frames if not pdf_viewer_frame(fr)]

# 오래된 누리집 라이브러리가 브라우저 기본 Map 을 자기 것으로 덮어쓰는 일이 있다
# (2026-10-19 경상북도 재난안전대책본부 gb.go.kr/gbsafe/main.tc). Playwright 는 결과를 돌려줄 때
# 페이지의 Map 으로 순환 참조를 세므로, 그런 페이지에서는 객체·배열 결과가 모두 None 이 되어
# 추출이 조용히 비거나 점검이 멈춘다. 그때만 결과를 JSON 문자열로 바꿔 받는다.
# 우리 스크립트도 new Map()·new Set()·Date 를 쓴다. 페이지 스크립트보다 먼저 도는 초기화 스크립트로
# 원래 기본 객체를 잡아 두고(NATIVE_HOOK), 감싼 스크립트 안에서 같은 이름으로 가려 그것을 쓰게 한다.
NATIVE_HOOK = """(() => { if (window.__hwonhiNative) return;
  Object.defineProperty(window, '__hwonhiNative', {value: Object.freeze({Map, Set, WeakMap, WeakSet, Date,
    // LAZY_HOOK 이 페이지 타이머를 세려고 감싸기 전의 것. 우리 쪽 양보·대기를 페이지 타이머로 세지 않는다
    setTimeout: window.setTimeout.bind(window)})});
})();"""
_JSON_TAG = "\u0000pw-json:"
_WRAP = ("(__a) => { const __n = window.__hwonhiNative || globalThis;"
         " const Map = __n.Map, Set = __n.Set, WeakMap = __n.WeakMap, WeakSet = __n.WeakSet, Date = __n.Date;"
         " const __arg = __a === '' ? undefined : JSON.parse(__a); let __v = (\n%s\n);"
         " if (typeof __v === 'function') __v = __v(__arg);"
         " const __out = v => /\\[native code\\]/.test(Function.prototype.toString.call(window.Map)) ? v"
         " : %s + JSON.stringify(v === undefined ? null : v);"
         " return __v && typeof __v.then === 'function' ? __v.then(__out) : __out(__v); }")


def _install_json_fallback():
    """Frame.evaluate(Page.evaluate 포함) 결과를 Map 이 덮어써진 페이지에서도 읽게 한다.

    playwright 1.63 의 내부 Frame.evaluate 를 감싼다. 요소 핸들처럼 JSON 으로 못 보내는 인자는
    원래 경로로 보낸다. 내부 구조가 바뀌어 감쌀 수 없으면 원래대로 둔다
    (tools/test_page_builtin_overrides.py 가 그런 변화를 잡는다).
    """
    try:
        from playwright._impl._frame import Frame
    except ImportError:
        return
    original = Frame.evaluate
    if getattr(original, "_json_fallback", False):
        return

    async def evaluate(self, expression, arg=None):
        try:
            sent = "" if arg is None else json.dumps(arg)
        except (TypeError, ValueError):
            return await original(self, expression, arg)
        try:
            value = await original(self, _WRAP % (expression.strip().rstrip(";"), json.dumps(_JSON_TAG)), sent)
        except Exception as exc:
            # 식이 아닌 문장 묶음은 감쌀 수 없다. 원래 경로로 보낸다
            if "SyntaxError" not in str(exc):
                raise
            return await original(self, expression, arg)
        if isinstance(value, str) and value.startswith(_JSON_TAG):
            return json.loads(value[len(_JSON_TAG):])
        return value

    evaluate._json_fallback = True
    Frame.evaluate = evaluate


_install_json_fallback()


def launch_browser(pw, headless=True):
    """(browser, 사용한 엔진 이름) 을 돌려준다."""
    try:
        return (pw.chromium.launch(channel=CHANNEL, headless=headless, args=LAUNCH_ARGS),
                f"설치된 브라우저({CHANNEL})")
    except Exception as exc:
        raise RuntimeError(
            "Microsoft Edge 를 실행하지 못했습니다. Edge 가 설치되어 있는지 확인해 주세요.\n"
            f"  원인 - {type(exc).__name__}: {exc}"
        ) from exc
