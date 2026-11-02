"""Cooperative cancellation and stage timing shared by scanner operations."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

_CURRENT = ContextVar("scan_control", default=None)

class ScanStopped(BaseException):
    # Broad page-error handlers must not turn cancellation into another retry.
    def __init__(self, reason):
        self.reason = reason

class ScanControl:
    def __init__(self, should_stop=None, time_limit=None, notify=None):
        self.should_stop = should_stop
        self.deadline = time.monotonic() + time_limit if time_limit else None
        self.notify = notify
        self.stage = "starting"
        self.url = ""
        self.timings = {}
        self.details = {}
        self.counts = {}

    def check(self):
        if self.should_stop and self.should_stop():
            raise ScanStopped("user")
        if self.deadline and time.monotonic() >= self.deadline:
            raise ScanStopped("time")

    @contextmanager
    def activate(self):
        token = _CURRENT.set(self)
        try:
            yield
        finally:
            _CURRENT.reset(token)

    @contextmanager
    def phase(self, name):
        self.check()
        self.stage = name
        start = time.monotonic()
        if self.notify:
            self.notify(name, self.url)
        try:
            yield
        finally:
            row = self.timings.setdefault(name, {"seconds": 0.0, "calls": 0})
            row["seconds"] += time.monotonic() - start
            row["calls"] += 1
        self.check()

def check_cancelled():
    control = _CURRENT.get()
    if control:
        control.check()

def wait(page, milliseconds):
    """Pump browser events in short, cancellable intervals."""
    end = time.monotonic() + max(0, milliseconds) / 1000
    while True:
        check_cancelled()
        left = (end - time.monotonic()) * 1000
        if left <= 0:
            return
        page.wait_for_timeout(min(left, 100))


def count(name, n=1):
    """시간이 아닌 횟수 계측 (눌러 본 후보 수, 다시 불러온 횟수 등)."""
    control = _CURRENT.get()
    if control:
        control.counts[name] = control.counts.get(name, 0) + n


@contextmanager
def detail(name):
    """Substage timings are separate from non-overlapping stage totals."""
    control = _CURRENT.get()
    start = time.monotonic()
    try:
        yield
    finally:
        if control:
            row = control.details.setdefault(name, {"seconds": 0.0, "calls": 0})
            row["seconds"] += time.monotonic() - start
            row["calls"] += 1
