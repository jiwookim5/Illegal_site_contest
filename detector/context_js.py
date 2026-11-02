"""추출 시점의 가까운 설명 제목과 정상 UI 문맥만 읽는다."""

LOCAL_CONTEXT = r"""
(el, readable, selector, label = null) => {
  // A child frame cannot borrow an unverified outer document's visible context.
  if (window.top !== window || !el) return null;
  const active = 'a[href],button,input,form,select,textarea,[onclick],[role="link"]';
  const unlinked = node => !node.closest(active) && !node.querySelector(active);
  const allReadable = (node, panel = null) =>
    [node, ...node.querySelectorAll('*')].every(item => readable(item, panel));
  if (label !== null) {
    // An explicit example in an ordinary tooltip is itself documentation.
    const action = 'a[href],form,input,select,textarea,[onclick],[role="link"]';
    if (/^(스팸|광고)\s*(문자|문구)\s*(예시|예제|인용)\s*[:：]/.test(label.trim()) &&
        !el.closest(action) && !el.querySelector(action) && readable(el))
      return {kind: 'quotation', source: 'documented_label'};
    return null;
  }
  if (!unlinked(el)) return null;
  const block = el.closest('blockquote,pre') || el.closest('p,li');
  const headingFor = (node, pattern, panel = null) => {
    const h = node.previousElementSibling;
    const text = (h?.textContent || '').trim();
    if (!h || !/^H[1-6]$/.test(h.tagName) || !text || text.length > 300 ||
        !pattern.test(text) || !allReadable(h, panel)) return null;
    return {text, location: selector(h)};
  };
  if (block && unlinked(block)) {
    // Only reciprocal, inactive ARIA tabs may explain display:none; additional hiding cannot.
    const panel = block.closest('[role="tabpanel"][hidden]');
    const tab = panel && document.getElementById(panel.getAttribute('aria-labelledby') || '');
    const inactive = panel && tab && tab.getAttribute('role') === 'tab' &&
      tab.getAttribute('aria-selected') === 'false' && tab.getAttribute('aria-controls') === panel.id &&
      readable(tab) && readable(panel.parentElement) ? panel : null;
    if (allReadable(block, inactive)) {
      const h = headingFor(block, /(예방|중독|회복|피해)/, inactive);
      if (h && /(상담|지원|회복)/.test(h.text))
        return {kind: 'service', heading: h, inactive_panel: inactive ? selector(inactive) : null};
    }
    if (allReadable(block)) {
      const code = block.tagName === 'PRE' && !!(el.closest('code') || block.querySelector('code'));
      const pattern = code ? /코드|구문|HTML|원문|예제|예시/i
        : /인용|예시|예제|스팸.*(문장|사례|문자)|(?:위장|수신).*문자|광고\s*문구/i;
      const h = headingFor(block, pattern);
      if (h) return {kind: 'quotation', heading: h};
    }
  }
  const cell = el.closest('td'), table = cell?.closest('table');
  if (!table || !unlinked(cell) || cell.colSpan !== 1 || cell.rowSpan !== 1 || !allReadable(cell)) return null;
  if (table.querySelector('[colspan]:not([colspan="1"]),[rowspan]:not([rowspan="1"])')) return null;
  const row = table.tHead?.rows[0] || table.rows[0], header = row?.cells[cell.cellIndex];
  const heading = table.caption || table.previousElementSibling;
  if (!header || header.tagName !== 'TH' || !heading || !/^(CAPTION|H[1-6]|P)$/.test(heading.tagName) ||
      [...row.cells].some(c => c.colSpan !== 1 || c.rowSpan !== 1)) return null;
  const text = (heading.textContent || '').trim(), name = (header.textContent || '').trim();
  if (text.length > 300 || name.length > 160 || !allReadable(header) || !allReadable(heading) ||
      !/인용|예시|예제|광고\s*문구|은닉\s*원문|evidence\s*text|삭제할\s*(메시지|문자)/i.test(name) ||
      !/예시|예제|테스트\s*시나리오|교육\s*자료|예방\s*사례|인용\s*문(?:구)?/i.test(text)) return null;
  return {kind: 'quotation', heading: {text, location: selector(heading)}, header: name};
}
"""
