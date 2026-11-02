"""Prioritize likely content pages without starving ordinary navigation."""
from collections import deque
import re
from urllib.parse import urlsplit

_CONTENT = re.compile(r"board|bbs|article|post|comment|reply|notice|view|list|page(?:no|index)?=", re.I)

class FairQueue:
    def __init__(self, urls=()):
        self.content, self.normal = deque(), deque()
        self.streak = 0
        for url in urls:
            self.append(url)

    def append(self, url):
        p = urlsplit(url)
        (self.content if _CONTENT.search(p.path + '?' + p.query) else self.normal).append(url)

    def popleft(self):
        if self.content and (not self.normal or self.streak < 3):
            self.streak += 1
            return self.content.popleft()
        self.streak = 0
        return self.normal.popleft()

    def __len__(self):
        return len(self.content) + len(self.normal)

    def __iter__(self):
        yield from self.content
        yield from self.normal
