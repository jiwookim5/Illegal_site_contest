"""robots.txt 해석이 표준(RFC 9309)·구글 방식과 같은지 확인한다."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
from politeness import USER_AGENT, Robots

# 대전시 누리집 robots.txt 의 꼴: Disallow: / 다음 빈 줄, 그 아래 Allow
DAEJEON = """User-agent: *
Disallow: /
Disallow: /RSA
Disallow: /drh/part/board

Allow: /english
Allow: /drh

User-agent: Yeti
User-agent: Googlebot
Allow: /
"""

# 중앙대 교육대학원(킴스큐) robots.txt 의 꼴: 와일드카드로 동작 주소를 막는다
KIMSQ = """User-agent: *
Disallow: /rb/admin
Disallow: /*mod=delete
Disallow: /*&a=
Disallow: /*?a=
Disallow: /*.pdf$
"""


def ok(text, path, agent=USER_AGENT):
    return Robots(text).can_fetch(agent, "https://example.go.kr" + path)


class RobotsTests(unittest.TestCase):
    def test_blank_line_does_not_end_group_and_longest_rule_wins(self):
        self.assertTrue(ok(DAEJEON, "/drh/board/boardNormalList.do?boardId=normal_0167"))
        self.assertTrue(ok(DAEJEON, "/english/index.do"))
        self.assertFalse(ok(DAEJEON, "/drh/part/board/list.do"))
        self.assertFalse(ok(DAEJEON, "/other"))

    def test_named_groups_share_rules(self):
        self.assertTrue(ok(DAEJEON, "/other", agent="Googlebot"))
        self.assertTrue(ok(DAEJEON, "/other", agent="Yeti"))

    def test_wildcards_and_end_anchor(self):
        self.assertFalse(ok(KIMSQ, "/?c=5&bid=notice&mod=delete&uid=156"))
        self.assertFalse(ok(KIMSQ, "/?m=bbs&bid=notice&a=scrap&uid=99"))
        self.assertFalse(ok(KIMSQ, "/files/a.pdf"))
        self.assertTrue(ok(KIMSQ, "/files/a.pdf?download=1"))
        self.assertTrue(ok(KIMSQ, "/?m=bbs&bid=notice&uid=178"))

    def test_tie_goes_to_allow_and_empty_rules_allow(self):
        self.assertTrue(ok("User-agent: *\nDisallow: /a\nAllow: /a\n", "/a/b"))
        self.assertTrue(ok("User-agent: *\nDisallow:\n", "/a"))
        self.assertTrue(ok("", "/a"))
        self.assertTrue(ok("﻿User-agent: *\nAllow: /\n", "/a"))
        self.assertFalse(ok("﻿User-agent: *\nDisallow: /\n", "/a"))


if __name__ == "__main__":
    unittest.main()
