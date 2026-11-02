"""주요 4종 밖의 은닉 경로를 훑는다.

텍스트 노드만 보면 놓치는 자리가 있다. 메타 태그, 속성값, 링크 주소에
광고를 심는 방식은 화면에 전혀 드러나지 않으면서 검색엔진에는 노출된다.
숨기지 않고 게시판·방명록에 그대로 올린 광고 글도 여기서 모은다.
"""

from selector_js import SELECTOR_OF as SEL_FN  # 요강의 location 규칙 (주요 4종과 같은 함수)

EXTRACT_EXTRA = r"""
({extra = true} = {}) => {
  const out = { metas: [], attrs: [], links: [], files: [], forms: [], texts: [] };

  const sel = SEL_FN;

  if (extra) {
  // 1) 제목과 메타 태그
  if (document.title) out.metas.push({ where: 'title', text: document.title, selector: 'title' });
  document.querySelectorAll('meta[name], meta[property]').forEach((m) => {
    const name = (m.getAttribute('name') || m.getAttribute('property') || '').toLowerCase();
    if (!['description', 'keywords', 'og:title', 'og:description'].includes(name)) return;
    const c = m.getAttribute('content') || '';
    if (c.trim()) out.metas.push({ where: name, text: c, selector: sel(m) });
  });

  // 2) 화면에 글자로 나오지 않는 속성값
  document.querySelectorAll('[alt],[title],[aria-label],[data-text]').forEach((el) => {
    ['alt', 'title', 'aria-label', 'data-text'].forEach((a) => {
      const v = el.getAttribute(a);
      if (v && v.trim().length > 3) out.attrs.push({ attr: a, text: v, selector: sel(el),
        context: a !== 'data-text' ? window.__hwonhiContext?.(el, v) : null });
    });
  });

  // 3) 바깥으로 나가는 링크 (글자가 없거나 주소 자체가 광고인 경우)
  const here = location.hostname;
  document.querySelectorAll('a[href]').forEach((a) => {
    let host = '';
    try { host = new URL(a.href, location.href).hostname; } catch (e) { return; }
    if (!host || host === here) return;
    out.links.push({ selector: sel(a), href: a.href, text: (a.textContent || '').trim().slice(0, 120) });
  });

  // 4) 첨부파일로 보이는 링크. 판별은 Python 쪽(attachments.looks_like_attachment)에서 한다.
  document.querySelectorAll('a[href]').forEach((a) => {
    if (!/^https?:/i.test(a.href)) return;
    out.files.push({ selector: sel(a), href: a.href, text: (a.textContent || '').trim().slice(0, 200) });
  });

  // 5) 검색 폼. 검색어가 결과 페이지에 반사되는지는 Python 쪽(search_reflect)에서 조회해 본다.
  //    브라우저가 실제로 전송할 값(숨은 필드, 선택된 옵션)을 그대로 모아 둔다.
  document.querySelectorAll('form').forEach((f) => {
    const fields = [], texts = [];
    Array.from(f.elements).forEach((el) => {
      if (!el.name || el.disabled) return;
      const tag = el.tagName.toLowerCase(), type = (el.type || '').toLowerCase();
      if (tag === 'input' && ['text', 'search', ''].includes(type)) {
        texts.push(el.name);
        fields.push({ name: el.name, value: '', text: true });
      } else if (tag === 'input' && ['checkbox', 'radio'].includes(type)) {
        if (el.checked) fields.push({ name: el.name, value: el.value });
      } else if (tag === 'input' && type === 'hidden') {
        fields.push({ name: el.name, value: el.value });
      } else if (tag === 'select') {
        fields.push({ name: el.name, value: el.value });
      }
    });
    if (!texts.length) return;                       // 글자 입력칸이 없으면 검색 폼이 아니다
    out.forms.push({
      selector: sel(f),
      action: f.action || location.href,              // 브라우저가 절대 주소로 풀어 준다
      method: (f.getAttribute('method') || 'get').toLowerCase(),
      fields: fields,
      texts: texts,
    });
  });

  }
  // 6) 화면에 그대로 보이는 글 덩어리. 게시판·방명록 도배 광고를 찾는다.
  //    글자 노드를 가장 가까운 블록 요소(문단·칸·목록 항목) 단위로 묶어, 바깥 틀이
  //    안쪽 문단의 글을 중복해서 품지 않게 한다.
  const blockOf = new Map(), styleOf = new Map();
  const disp = (el) => {
    if (!styleOf.has(el)) styleOf.set(el, getComputedStyle(el).display);
    return styleOf.get(el);
  };
  const SKIP = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'TEXTAREA', 'OPTION', 'TITLE']);
  const walker = document.createTreeWalker(document.body || document.documentElement, NodeFilter.SHOW_TEXT);
  const order = [];
  let n, budget = 20000;
  while ((n = walker.nextNode()) && budget-- > 0) {
    const t = n.nodeValue;
    if (!t || !t.trim()) continue;
    let el = n.parentElement;
    if (!el || SKIP.has(el.tagName)) continue;
    let block = el;
    while (block.parentElement && block !== document.body && disp(block).startsWith('inline')) {
      block = block.parentElement;
    }
    if (!blockOf.has(block)) { blockOf.set(block, []); order.push(block); }
    blockOf.get(block).push(n);
  }
  const kept = [];
  window.__hwonhiBlocks = kept;        // 광고로 판정된 것만 나중에 선택자를 만든다
  for (const block of order) {
    if (out.texts.length >= 1500) break;
    // 숨긴 글은 주요 4종 판정이 맡는다. 여기서는 실제로 보이는 것만 모은다.
    const r = block.getBoundingClientRect();
    if (r.width < 2 || r.height < 2) continue;
    if (block.checkVisibility && !block.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
    const parts = [];
    for (const tn of blockOf.get(block)) {
      const p = tn.parentElement;
      if (p !== block && p.checkVisibility && !p.checkVisibility({ opacityProperty: true, visibilityProperty: true })) continue;
      // checkVisibility alone misses transparent color, clipping and offscreen children.
      if (window.__hwonhiReadable && !window.__hwonhiReadable(p)) continue;
      parts.push(tn.nodeValue);
    }
    const text = parts.join(' ').replace(/\s+/g, ' ').trim();
    if (text.length < 4) continue;
    kept.push(block);
    // 도배 글은 긴 문단 끝에 광고 해시태그를 몰아 둔다 (광주교육청 배너모음 2,662자 문단). 1,000자에서 자르면 놓친다
    out.texts.push({ i: kept.length - 1, text: text.slice(0, 6000), context: window.__hwonhiContext?.(block) });
  }

  return out;
}
"""

EXTRACT_EXTRA = EXTRACT_EXTRA.replace("SEL_FN", SEL_FN.strip())

# 광고로 판정된 글 덩어리의 선택자만 만든다. 모든 덩어리에 만들면 페이지가 클 때 느리다.
BLOCK_SELECTORS = r"""
({ids, reported}) => {
  const sel = SEL_FN;
  const kept = window.__hwonhiBlocks || [];
  const previous = reported.map(row => ({el: document.querySelector(row.selector), text: row.text}));
  const compact = text => text.replace(/\s+/g, '').trim();
  return ids.map(i => {
    const block = kept[i];
    if (!block) return null;
    const text = compact(block.textContent || '');
    const duplicate = previous.some(row => row.el && (row.el === block ||
      ((block.contains(row.el) || row.el.contains(block)) && window.__hwonhiReadable?.(row.el) &&
       (text.includes(compact(row.text)) || compact(row.text).includes(text)))));
    return duplicate ? null : sel(block);
  });
}
""".replace("SEL_FN", SEL_FN.strip())
