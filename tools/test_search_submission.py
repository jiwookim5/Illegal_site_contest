"""외부 호출 없는 검색 제출 스키마·분류·병합 회귀."""
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'detector'))
from search_submission import document, export, publish, summary
from output_schema import check


def run():
    source = dict(engine='google', page=1, search_url='https://www.google.com/search?q=test',
                  searched_at='2026-10-19T10:00:00+09:00',
                  title='카지노 가입 보너스 텔레그램 @casino777', snippet='신규 가입 보너스 지급')
    return dict(target='example.test', started_at='2026-10-19T10:00:00+09:00',
                finished_at='2026-10-19T10:01:00+09:00',
                results=[dict(url='https://example.test/post', sources=[source], status='미검사')])


class SubmissionTests(unittest.TestCase):
    def test_cli_saved_search_resume_publishes_to_original_output(self):
        import search_assist

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            output = root / 'original-output'
            folder = output / 'search_results' / 'saved'
            folder.mkdir(parents=True)
            data = dict(run(), queries=[], notes=[], stopped=False, limit_reached=False)
            # 이미 회수된 검색은 외부 호출 없이 다시 저장한다. 실행 위치가 달라도 원래 출력에 합쳐야 한다.
            for saved_folder in (folder, folder / 'google'):
                with self.subTest(folder=saved_folder.name):
                    saved_folder.mkdir(exist_ok=True)
                    saved = saved_folder / 'results.json'
                    saved.write_text(json.dumps(data), encoding='utf-8')
                    with patch.object(search_assist, 'ROOT', root / 'elsewhere'), \
                            patch.object(sys, 'argv', ['search_assist.py', '--resume-search', str(saved)]):
                        self.assertEqual(search_assist.main(), 0)
                    self.assertTrue((saved_folder / 'result_extra.json').exists())
                    published = json.loads((output / 'result_extra.json').read_text(encoding='utf-8'))
                    self.assertEqual(published['meta']['entry_url'], 'https://example.test')
                    self.assertEqual(len(published['findings']), 1)
            self.assertFalse((output / 'search_results' / 'result_extra.json').exists())
            self.assertFalse((root / 'elsewhere' / 'result_extra.json').exists())
            self.assertFalse((output / 'review.sqlite3').exists())

    def test_classification_and_no_false_deletion(self):
        for status, http, suffix, code in [
            ('미검사', None, '', 'SEARCH_INDEXED_AD'),
            ('삭제 응답', 404, '', 'SEARCH_REMOVED_AD'),
            ('삭제 응답', 410, '', 'SEARCH_REMOVED_AD'),
            ('확인 불가', 403, '', 'SEARCH_INDEXED_AD'),
            ('삭제 안내 의심', 200, '', 'SEARCH_INDEXED_AD'),
            ('파라미터 반영', 200, '?q=카지노+가입+보너스', 'SEARCH_PARAMETER_AD')]:
            with self.subTest(status=status, http=http):
                data = run()
                data['results'][0].update(status=status, http_status=http)
                data['results'][0]['url'] += suffix
                result = document(data)['findings'][0]
                self.assertTrue(result['extra_finding'].startswith(code))
                self.assertIn(status, result['evidence_text'])
                self.assertEqual(result['technique'], 'ETC')

    def test_summary_counts_by_type(self):
        data = run()
        data['results'].append(dict(data['results'][0], url='https://example.test/gone', http_status=404, status='삭제 응답'))
        self.assertEqual(summary(data), {'count': 2, 'types': {'SEARCH_INDEXED_AD': 1, 'SEARCH_REMOVED_AD': 1}})
        data['results'] = []
        self.assertEqual(summary(data), {'count': 0, 'types': {}})

    def test_url_only_normal_and_out_of_scope_excluded(self):
        data = run()
        data['results'][0]['url'] += '?q=카지노+가입+보너스'
        data['results'][0]['sources'][0].update(title='도서관 운영 안내', snippet='방문 안내')
        self.assertEqual(document(data)['findings'], [])
        # 정상 공공 예방·단속 안내문 스니펫은 광고로 오탐하지 않는다
        data = run()
        data['results'][0]['sources'][0].update(title='경찰청 마약류 범죄 특별단속 안내 및 대포통장 처벌 경고', snippet='신고 및 상담 안내')
        self.assertEqual(document(data)['findings'], [])
        data = run()
        data['results'][0]['url'] = 'https://outside.test/post'
        self.assertEqual(document(data)['findings'], [])

    def test_live_and_duplicate_sources(self):
        data = run()
        row = data['results'][0]
        row.update(status='광고 탐지', findings=[dict(location='div > span', evidence_text='광고 원문')])
        row['sources'] *= 2
        result = document(data)['findings']
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0]['extra_finding'].startswith('SEARCH_LIVE_AD'))
        self.assertIn('광고 원문', result[0]['evidence_text'])
        self.assertIn('div > span', result[0]['location'])

    def test_schema_preservation_and_idempotent_resume(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'search_results' / 'one'
            folder.mkdir(parents=True)
            baseline = document(run())
            baseline['findings'][0].update(id='e_001', extra_finding='VISIBLE_AD')
            path = root / 'result_extra.json'
            path.write_text(json.dumps(baseline), encoding='utf-8')
            (root / 'result.json').write_bytes(b'original-main-result')
            data = run()
            for _ in range(2):
                publish(data, folder, root, lambda _: None)
            merged = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(len(merged['findings']), 2)
            self.assertEqual(merged['findings'][0], baseline['findings'][0])
            data['results'][0]['http_status'] = 410
            publish(data, folder, root, lambda _: None)
            self.assertEqual(len(json.loads(path.read_text(encoding='utf-8'))['findings']), 2)
            for result in (path, folder / 'result_extra.json'):
                errors, items, _, _ = check(str(result), extra=True)
                self.assertFalse(errors or items, (errors, items))
                self.assertFalse(result.read_bytes().startswith(b'\xef\xbb\xbf'))
            self.assertEqual((root / 'result.json').read_bytes(), b'original-main-result')
            another = folder.parent / 'two'
            another.mkdir()
            publish(data, another, root, lambda _: None)
            self.assertEqual(len(json.loads(path.read_text(encoding='utf-8'))['findings']), 2)

    def test_other_target_and_corruption_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'search_results' / 'one'
            folder.mkdir(parents=True)
            data = run()
            old = document(data)
            old['meta']['entry_url'] = 'https://other.test/'
            path = root / 'result_extra.json'
            path.write_text(json.dumps(old), encoding='utf-8')
            original = path.read_bytes()
            publish(data, folder, root, lambda _: None)
            self.assertEqual(path.read_bytes(), original)
            path.write_text('{broken', encoding='utf-8')
            with self.assertRaises(ValueError):
                publish(data, folder, root, lambda _: None)
            self.assertEqual(path.read_text(), '{broken')

    def test_port_target_merges_with_original_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / 'search_results' / 'one'
            folder.mkdir(parents=True)
            baseline = document(run())
            baseline['meta']['entry_url'] = 'http://127.0.0.1:8768/www/main'
            path = root / 'result_extra.json'
            path.write_text(json.dumps(baseline), encoding='utf-8')
            data = run()
            data['target'] = '127.0.0.1'
            data['results'][0]['url'] = 'http://127.0.0.1:8768/post'
            publish(data, folder, root, lambda _: None)
            merged = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(merged['meta']['entry_url'], 'http://127.0.0.1:8768/www/main')
            self.assertTrue(any(f['id'].startswith('e_search_') for f in merged['findings']))


if __name__ == '__main__':
    unittest.main(verbosity=2)
