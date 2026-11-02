"""저장한 동일 검색의 HTML/JSON/수집 증거 비교. 네트워크 요청·HTML 실행 없음."""
import argparse
import html
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class Headings(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchor = None
        self.in_heading = False
        self.links = []
        self.text = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'):
            self.skip += 1
        if tag == 'a':
            self.anchor = {'href': dict(attrs).get('href', ''), 'title': '', 'heading': False}
        if tag == 'h3' and self.anchor is not None:
            self.in_heading = True
            self.anchor['heading'] = True

    def handle_endtag(self, tag):
        if tag in ('script', 'style'):
            self.skip = max(0, self.skip - 1)
        if tag == 'h3':
            self.in_heading = False
        if tag == 'a' and self.anchor is not None:
            if self.anchor['heading']:
                self.links.append(self.anchor)
            self.anchor = None

    def handle_data(self, value):
        if not self.skip:
            self.text.append(value)
            if self.in_heading and self.anchor is not None:
                self.anchor['title'] += value


def identity(url):
    """Google /goto와 /url의 불투명 토큰도 이동 없이 대조한다."""
    p = urlsplit(url)
    if p.path in ('/goto', '/url') and p.hostname in (None, 'www.google.com', 'www.google.co.kr'):
        return (parse_qs(p.query).get('url') or parse_qs(p.query).get('q') or [url])[0]
    return url


def compare(data, markup, evidence):
    parser = Headings()
    parser.feed(markup)
    organic = data.get('organic_results', [])
    lookup = {}
    for item in organic:
        for field in ('link', 'redirect_link'):
            if item.get(field):
                lookup[identity(item[field])] = item['link']
    rows = []
    stored = {h['href'] for h in evidence.get('hits', [])}
    for anchor in parser.links:
        url = lookup.get(identity(anchor['href']))
        rows.append({'title': anchor['title'], 'html_href': anchor['href'],
                     'json_url': url, 'in_saved_evidence': url in stored if url else False})
    mapped = {r['json_url'] for r in rows if r['json_url']}
    notices = data.get('dmca_messages') or {}
    return {'search_id': data.get('search_metadata', {}).get('id'),
            'evidence_search_id_matches': data.get('search_metadata', {}).get('id') == evidence.get('search_id'),
            'html_heading_count': len(rows), 'json_organic_count': len(organic),
            'saved_hit_count': len(stored), 'matched_html_count': sum(bool(r['json_url']) for r in rows),
            'unmatched_html_count': sum(not r['json_url'] for r in rows),
            'json_missing_from_html': [i['link'] for i in organic if i['link'] not in mapped],
            'json_missing_from_saved': [i['link'] for i in organic if i['link'] not in stored],
            'provider_notices': [m.get('content', '') for m in notices.get('messages', [])],
            'rows': rows, 'html_text': ' '.join(parser.text),
            'limitation': 'h3 제목 링크 대조. 일치하지 않은 링크는 검토 후보이며 자동 누락 확정이 아님. HTML은 실행하지 않음.'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--json', type=Path, required=True)
    p.add_argument('--html', type=Path, required=True)
    p.add_argument('--evidence', type=Path, required=True)
    p.add_argument('--out', type=Path, required=True)
    a = p.parse_args()
    result = compare(json.loads(a.json.read_text(encoding='utf-8')), a.html.read_text(encoding='utf-8'),
                     json.loads(a.evidence.read_text(encoding='utf-8')))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out/'comparison.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    esc = html.escape
    rows = ''.join('<tr><td>'+esc(r['title'])+'</td><td>'+esc(r['json_url'] or 'JSON 대응 링크 미확인')+
                   '</td><td>'+str(r['in_saved_evidence'])+'</td></tr>' for r in result['rows'])
    summary = {k:v for k,v in result.items() if k not in ('rows','html_text')}
    doc = '<!doctype html><meta charset="utf-8"><title>SerpApi 원본 비교</title><style>body{font:16px sans-serif;margin:30px}td{border:1px solid #aaa;padding:10px;overflow-wrap:anywhere}pre{white-space:pre-wrap}</style>'
    doc += '<h1>동일 검색 ID의 원본 HTML · JSON · 저장 결과 대조</h1><pre>'+esc(json.dumps(summary, ensure_ascii=False, indent=2))+'</pre>'
    doc += '<table><tr><th>HTML 검색 제목</th><th>JSON URL</th><th>저장 여부</th></tr>'+rows+'</table>'
    doc += '<h2>원본 HTML의 텍스트 추출본</h2><p>원본 화면 캡처가 아닌 실행 없는 텍스트 추출입니다.</p><pre>'+esc(result['html_text'])+'</pre>'
    (a.out/'comparison.html').write_text(doc, encoding='utf-8')
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == '__main__':
    main()
