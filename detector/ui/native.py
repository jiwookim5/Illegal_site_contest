"""네이티브 창으로 화면을 띄운다.

Windows 11 에 기본 탑재된 WebView2 를 써서 브라우저 창이 아닌
자체 창으로 연다. 런타임이나 모듈이 없으면 쓸 수 없다고 알려 주고,
호출 쪽이 브라우저 창으로 물러나게 한다.
"""
import sys
import threading

WINDOW_W, WINDOW_H = 1200, 820
MIN_W, MIN_H = 940, 620


def available():
    """이 환경에서 네이티브 창을 띄울 수 있는가."""
    if sys.platform != "win32":
        return False
    try:
        import webview  # noqa: F401
        import clr      # noqa: F401  (pythonnet)
    except Exception:
        return False
    return True


def run(url, title, on_close=None, register_close=None):
    """창이 닫힐 때까지 돌아오지 않는다. 실패하면 False."""
    try:
        import webview

        window = webview.create_window(title, url,
                              width=WINDOW_W, height=WINDOW_H,
                              min_size=(MIN_W, MIN_H),
                              text_select=True)
        allowed = threading.Event()

        def closing():
            if on_close and not allowed.is_set():
                on_close()
                return False

        def close():
            allowed.set()
            window.destroy()

        window.events.closing += closing
        if register_close:
            register_close(close)
        webview.start()
        return True
    except Exception as exc:
        print(f"  네이티브 창을 열지 못했습니다({type(exc).__name__}). 브라우저 창으로 엽니다.")
        return False
