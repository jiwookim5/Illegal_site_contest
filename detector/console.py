"""콘솔 창 처리.

화면 모드에서 검은 콘솔 창이 함께 뜨면 앱처럼 보이지 않는다. 그래서 창 없는
프로그램(GUI 서브시스템)으로 만들고, 터미널에서 실행했을 때만 그 터미널에
출력을 붙인다. 바탕화면에서 더블클릭하면 콘솔은 나타나지 않는다.
"""
import os
import sys

ATTACH_PARENT_PROCESS = -1


def _ensure_streams():
    """창 없는 빌드에서는 표준 출력이 없어 print 가 실패한다. 빈 출구를 달아 둔다.

    출력을 파일·파이프로 돌리면(`훤히.exe --cli ... > log.txt`, 작업 스케줄러) 한국어 Windows 에서는
    cp949 로 쓰는데, 도움말의 '—' 처럼 cp949 에 없는 글자를 만나면 UnicodeEncodeError 로 죽는다.
    그런 글자는 '?' 로 바꿔 쓰고 계속한다.
    """
    for name in ("stdout", "stderr"):
        stream = getattr(sys, name, None)
        if stream is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
            continue
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass


def attach_to_parent(allocate_if_missing=False):
    """터미널에서 실행된 경우 그 터미널에 출력을 연결한다.

    allocate_if_missing 이 참이면 붙을 터미널이 없을 때 새로 하나 띄운다.
    터미널 모드(--cli)로 실행했는데 아무 것도 보이지 않는 상황을 막기 위함이다.
    """
    original = {name: getattr(sys, name, None) for name in ("stdout", "stderr")}
    _ensure_streams()
    if sys.platform != "win32" or not getattr(sys, "frozen", False):
        return False
    try:
        import ctypes
        from ctypes import wintypes
        import msvcrt
        k32 = ctypes.windll.kernel32
        k32.GetStdHandle.argtypes = [wintypes.DWORD]
        k32.GetStdHandle.restype = wintypes.HANDLE
        k32.GetFileType.argtypes = [wintypes.HANDLE]
        redirected = set()
        for name, std_id in (("stdout", -11), ("stderr", -12)):
            handle = k32.GetStdHandle(std_id & 0xffffffff)
            if handle and k32.GetFileType(handle) in (1, 3):  # disk / pipe
                redirected.add(name)
                if original[name] is None:
                    # Duplicate the inherited handle: Python owns only its duplicate.
                    k32.GetCurrentProcess.restype = wintypes.HANDLE
                    k32.DuplicateHandle.argtypes = [wintypes.HANDLE, wintypes.HANDLE, wintypes.HANDLE,
                                                  ctypes.POINTER(wintypes.HANDLE), wintypes.DWORD,
                                                  wintypes.BOOL, wintypes.DWORD]
                    current = k32.GetCurrentProcess()
                    duplicate = wintypes.HANDLE()
                    if k32.DuplicateHandle(current, handle, current, ctypes.byref(duplicate), 0, False, 2):
                        fd = msvcrt.open_osfhandle(duplicate.value, os.O_WRONLY)
                        setattr(sys, name, os.fdopen(fd, "w", encoding="utf-8", buffering=1))
        if len(redirected) == 2:
            return True
        if not k32.AttachConsole(ATTACH_PARENT_PROCESS):
            if not allocate_if_missing or not k32.AllocConsole():
                return False
        for name in ("stdout", "stderr"):
            if name not in redirected:
                setattr(sys, name, open("CONOUT$", "w", encoding="utf-8", buffering=1))
        return True
    except Exception:
        return False
