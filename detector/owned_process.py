"""Own only the scan subprocess tree; closing the job also handles parent crashes."""
import ctypes
from ctypes import wintypes
import os
import signal

class ProcessTree:
    def __init__(self, process, name=None):
        self.process = process
        self.handle = None
        if os.name != "nt":
            return
        class Limits(ctypes.Structure):
            _fields_ = [("process_time", ctypes.c_int64), ("job_time", ctypes.c_int64),
                        ("flags", wintypes.DWORD), ("minimum", ctypes.c_size_t),
                        ("maximum", ctypes.c_size_t), ("active", wintypes.DWORD),
                        ("affinity", ctypes.c_size_t), ("priority", wintypes.DWORD),
                        ("scheduling", wintypes.DWORD)]
        class IO(ctypes.Structure):
            _fields_ = [(name, ctypes.c_uint64) for name in
                        ("read_ops", "write_ops", "other_ops", "read_bytes", "write_bytes", "other_bytes")]
        class Extended(ctypes.Structure):
            _fields_ = [("limits", Limits), ("io", IO), ("process_memory", ctypes.c_size_t),
                        ("job_memory", ctypes.c_size_t), ("peak_process", ctypes.c_size_t),
                        ("peak_job", ctypes.c_size_t)]
        k = ctypes.WinDLL("kernel32", use_last_error=True)
        k.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
        k.CreateJobObjectW.restype = wintypes.HANDLE
        k.SetInformationJobObject.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p, wintypes.DWORD]
        k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
        k.TerminateJobObject.argtypes = [wintypes.HANDLE, wintypes.UINT]
        k.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = k.CreateJobObjectW(None, name)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        info = Extended()
        info.limits.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
        if not (k.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)) and
                k.AssignProcessToJobObject(handle, int(process._handle))):
            error = ctypes.get_last_error()
            k.CloseHandle(handle)
            raise ctypes.WinError(error)
        self.kernel, self.handle = k, handle

    def close(self):
        if self.handle:
            handle, self.handle = self.handle, None
            self.kernel.TerminateJobObject(handle, 1)
            self.kernel.CloseHandle(handle)
        elif os.name != "nt":
            try:
                os.killpg(self.process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        elif self.process.poll() is None:
            self.process.kill()


def join_job(name):
    """Join from the real Python/EXE worker too (venv launchers may fork early)."""
    if os.name != "nt":
        return
    k = ctypes.WinDLL("kernel32", use_last_error=True)
    k.OpenJobObjectW.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.LPCWSTR]
    k.OpenJobObjectW.restype = wintypes.HANDLE
    k.GetCurrentProcess.restype = wintypes.HANDLE
    k.IsProcessInJob.argtypes = [wintypes.HANDLE, wintypes.HANDLE, ctypes.POINTER(wintypes.BOOL)]
    k.AssignProcessToJobObject.argtypes = [wintypes.HANDLE, wintypes.HANDLE]
    k.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = k.OpenJobObjectW(0x0001 | 0x0004, False, name)  # assign + query
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        current = k.GetCurrentProcess()
        assigned = wintypes.BOOL()
        if not k.IsProcessInJob(current, handle, ctypes.byref(assigned)):
            raise ctypes.WinError(ctypes.get_last_error())
        if not assigned.value and not k.AssignProcessToJobObject(handle, current):
            raise ctypes.WinError(ctypes.get_last_error())
    finally:
        # Only the supervisor retains a handle; its death closes the job.
        k.CloseHandle(handle)
