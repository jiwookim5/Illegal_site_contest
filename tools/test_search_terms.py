"""검색 보조 탐색의 유형별 고정 광고단어 검증. 외부 호출 없음."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'detector'))
import lexicon
from search_terms import GROUPS, MAX_TERMS, SEARCH_ONLY, expand, groups


class SearchTermTests(unittest.TestCase):
    def test_fixed_words_are_in_the_detection_lexicon(self):
        # 검색에 쓰는 단어와 점검 사전이 어긋나지 않게 한다. 띄어 쓴 항목은 낱말마다 확인한다
        known = {w.lower() for words in lexicon._BUILTIN.values() for w in words}
        parts = {p for _, _, words in GROUPS for w in words for p in w.split()}
        missing = sorted(p for p in parts if p.lower() not in known)
        # 사전에 없는 말은 SEARCH_ONLY 에 적어 두며, 사전에 들어오면 그 목록에서 지워야 한다
        self.assertEqual(missing, sorted(SEARCH_ONLY))
        self.assertEqual(sorted(set(SEARCH_ONLY) & known), [])

    def test_drug_slang_search_terms_are_judged_by_sale_slang_rule(self):
        # 시원한술·찬술은 사전 목록이 아니라 판매 은어 규칙으로 판정한다. 검색에 쓰는 말이 판정에서 빠지지 않게 한다
        from findings import classify
        for word in ("시원한술", "찬술"):
            self.assertIn(word, SEARCH_ONLY)
            self.assertTrue(classify(f"{word}삽니다 텔@abcd1234")['is_ad'], word)
            self.assertFalse(classify(f"{word}삽니다 안내 문의 033-670-2777")['is_ad'], word)

    def test_groups_have_no_duplicates_and_leave_room_for_extra_terms(self):
        words = [w for _, _, ws in GROUPS for w in ws]
        self.assertEqual(len(words), len(set(words)))
        self.assertEqual([g['id'] for g in groups()], [i for i, _, _ in GROUPS])
        # 점검에서 찾은 단어(최대 5개)를 더해도 상한을 넘지 않는다
        self.assertLessEqual(len(words) + 5, MAX_TERMS)

    def test_expand_merges_dedups_and_rejects_unknown_group(self):
        terms = expand(['gambling'], ['먹튀', ' 가입머니 ', ''])
        self.assertEqual(terms[:5], GROUPS[0][2])
        self.assertEqual(terms[5:], ['가입머니'])
        self.assertEqual(expand([], ['a']), ['a'])
        with self.assertRaises(ValueError):
            expand(['nope'])
        with self.assertRaises(ValueError):
            expand('gambling')


if __name__ == '__main__':
    unittest.main(verbosity=2)
