"""화면을 앱 창으로 띄운다.

브라우저 탭이 아니라 주소창·탭이 없는 독립 창으로 열어야 도구처럼 보인다.
Windows 11 에는 Edge 가 기본 탑재되어 있으므로 Edge 의 앱 모드를 쓰고,
없으면 Chrome, 그것도 없으면 기본 브라우저로 물러난다.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import time
import webbrowser
from owned_process import ProcessTree

WINDOWS_CANDIDATES = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]
POSIX_CANDIDATES = ["microsoft-edge", "google-chrome", "chromium"]


def _browser_path():
    """창을 띄울 브라우저를 고른다. 없으면 None (기본 브라우저로 연다)."""
    if sys.platform == "win32":
        for path in WINDOWS_CANDIDATES:
            if os.path.exists(path):
                return path
    else:
        for name in POSIX_CANDIDATES:
            found = shutil.which(name)
            if found:
                return found
    return None


class AppWindow:
    """Own only this launch's browser process tree and temporary profile."""

    def __init__(self, name, process=None, tree=None, profile=None):
        self.name, self.process, self.tree, self.profile = name, process, tree, profile

    def close(self):
        if self.tree:
            self.tree.close()
            self.tree = None
        if self.process:
            self.process.wait(timeout=5)
        if self.profile:
            # Edge's launcher may already be gone while its children release profile files.
            for delay in (0.1, 0.2, 0.4, 0.8, 1.6):
                self.profile.cleanup()
                if not os.path.exists(self.profile.name):
                    self.profile = None
                    break
                time.sleep(delay)


def open_app_window(url):
    """사용한 창과 해당 실행만 닫는 핸들을 돌려준다."""
    exe = _browser_path()
    if not exe:
        webbrowser.open(url)
        return AppWindow("기본 브라우저")

    # 사용자의 평소 프로필을 건드리지 않도록 전용 프로필 폴더를 쓴다.
    # 같은 폴더를 재사용하면 이전 실행의 창 크기가 되살아나고, 살아 있는
    # 이전 창이 있으면 새 요청이 그쪽으로 넘어가 버린다. 실행마다 분리한다.
    profile = tempfile.TemporaryDirectory(prefix="ad_detector_ui_", ignore_cleanup_errors=True)
    args = [
        exe,
        f"--app={url}",
        f"--user-data-dir={profile.name}",
        "--disable-background-mode",
        # 크기·위치는 지정하지 않는다. 화면 배율(125~150%)에서 DIP 환산이 어긋나
        # 창이 화면 밖으로 밀려나는 일이 있어, 브라우저가 작업 영역에 맞추도록 맡긴다.
        "--no-first-run",
        "--no-default-browser-check",
        # 자동화용 빌드임을 알리는 안내 막대를 띄우지 않는다.
        "--test-type",
        "--disable-infobars",
        # Edge 는 Windows 계정으로 자동 로그인해 동기화 안내창을 띄운다.
        # 점검 도구 화면에 개인 계정이 노출되지 않도록 막는다.
        "--disable-sync",
        # 창을 최소화하거나 다른 창 뒤에 두면 Edge 가 타이머를 1분에 한 번으로 늦춘다. 그러면 화면이 보내는
        # 생존 신호(5초마다)가 끊겨 훤히가 '창이 닫혔다'고 보고 꺼진다. 점검 도구 창은 늦추지 않는다.
        "--disable-background-timer-throttling",
        "--disable-renderer-backgrounding",
        "--disable-backgrounding-occluded-windows",
        "--disable-features=Translate,AutofillServerCommunication,ChromeWhatsNewUI,"
        "msImplicitSignin,msEdgeIdentitySignIn,EdgeSyncPromo,ShowSyncPromoOnFirstRun,"
        "SigninPromo,msSignInPromo,msEdgeShoppingAssistant,msWebAssist,IntensiveWakeUpThrottling",
    ]
    process = None
    try:
        kwargs = {}
        if sys.platform == "win32":
            kwargs["creationflags"] = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        else:
            kwargs["start_new_session"] = True
        process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **kwargs)
        tree = ProcessTree(process)
        return AppWindow(f"앱 창({os.path.basename(exe)})", process, tree, profile)
    except Exception:
        if process and process.poll() is None:
            process.terminate()
            process.wait(timeout=5)
        profile.cleanup()
        webbrowser.open(url)
        return AppWindow("기본 브라우저")
