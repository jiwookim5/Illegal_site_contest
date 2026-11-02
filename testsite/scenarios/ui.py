"""Shared controls for the local fixture documents."""
from html import escape
import json
import re


def finish_routes(routes: dict, root: str) -> dict:
    """Give shared detail controls real destinations without changing targets."""
    for response in routes.values():
        if not response.get("content_type", "text/html").startswith("text/html"):
            continue
        html = response["body"]
        list_url = response.get("list_url", root)
        html = re.sub(
            r'<(?:button|span)\b[^>]*class="btn btn-primary"[^>]*>목록</(?:button|span)>',
            f'<a class="btn btn-primary" data-fixture-list target="_top" href="{escape(list_url, quote=True)}">목록</a>', html)
        html = re.sub(
            r'<(?:button|span)\b[^>]*class="btn"[^>]*>인쇄</(?:button|span)>',
            '<button type="button" class="btn" onclick="window.print()">인쇄</button>', html)
        html = re.sub(
            r'<(?:button|span)\b[^>]*class="btn"[^>]*>공유</(?:button|span)>',
            '<button type="button" class="btn" data-fixture-share>공유</button>'
            '<span role="status" data-share-status></span>', html)
        html = re.sub(
            r'<(?:button|span)\b[^>]*class="btn-file-action"[^>]*>(?:미리보기|다운로드)</(?:button|span)>',
            '', html)
        # These documents are examples, not downloadable files.
        html = html.replace('첨부파일 (1건)', '첨부파일 예시 (실제 파일 없음)')
        html = html.replace('<strong>첨부파일</strong>', '<strong>첨부파일 예시 (실제 파일 없음)</strong>')
        html = re.sub(r'<span class="btn"[^>]*>다운로드</span>', '', html)
        scripts = []
        if response.get("list_return_urls"):
            scripts.append("""
function listKey(url) { url.hash = ''; url.searchParams.sort(); return url.href; }
try {
  const origin = new URL(document.referrer);
  const allowed = ALLOWED_LISTS.map(path => listKey(new URL(path, location.href)));
  if (origin.origin === location.origin && allowed.includes(listKey(origin))) {
    document.querySelectorAll('[data-fixture-list]').forEach(link => link.href = origin.href);
  }
} catch (error) { /* Direct visits use the authored default list URL. */ }
""".replace("ALLOWED_LISTS", json.dumps(response["list_return_urls"])))
        if 'role="tablist"' in html:
            scripts.append("""
document.querySelectorAll('[role="tablist"]').forEach(function(group) {
  const tabs = Array.from(group.querySelectorAll('[role="tab"]'));
  function updateStops() {
    tabs.forEach(tab => tab.tabIndex = tab.getAttribute('aria-selected') === 'true' ? 0 : -1);
  }
  tabs.forEach(tab => tab.addEventListener('click', updateStops));
  group.addEventListener('keydown', function(event) {
    const index = tabs.findIndex(tab => tab.contains(event.target));
    if (index < 0) return;
    let next;
    if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
    else if (event.key === 'ArrowLeft') next = (index + tabs.length - 1) % tabs.length;
    else if (event.key === 'Home') next = 0;
    else if (event.key === 'End') next = tabs.length - 1;
    else return;
    event.preventDefault();
    tabs[next].focus();
    tabs[next].click();
    updateStops();
  });
  updateStops();
});
""")
        if 'data-fixture-share' in html:
            scripts.append("""
document.querySelectorAll('[data-fixture-share]').forEach(function(button) {
  button.addEventListener('click', async function() {
    var status = button.parentElement.querySelector('[data-share-status]');
    try {
      await navigator.clipboard.writeText(location.href);
      status.textContent = '주소를 복사했습니다.';
    } catch (error) {
      status.textContent = '공유 주소: ' + location.href;
    }
  });
});
""")
        if scripts:
            html = html.replace('</body>', '<script>' + '\n'.join(scripts) + '</script></body>')
        response["body"] = html
    return routes
