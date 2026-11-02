"""CSS geometry shared by text and iframe inspection."""

VISIBILITY_HELPERS = r"""
  function len(v, base) {
    v = (v || '').trim();
    if (v.endsWith('%')) return parseFloat(v) / 100 * base;
    return parseFloat(v) || 0;
  }

  // clip-path 가 남기는 영역이 사실상 0 인가. 원·타원 반지름 0, inset 이 서로 맞닿음, 넓이 0 인 다각형.
  function clipPathZero(cp, rect) {
    if (!cp || cp === 'none') return false;
    const w = rect.width, h = rect.height;
    let m;
    // clip-path:url(#id) 가 가리키는 <clipPath> 의 도형 넓이가 0 이면 아무것도 그리지 않는다
    if ((m = cp.match(/url\(\s*["']?#([^"')]+)["']?\s*\)/))) {
      const ref = document.getElementById(m[1]);
      if (!ref || ref.tagName.toLowerCase() !== 'clippath') return false;
      let area = 0;
      for (const c of ref.children) {
        try { const b = c.getBBox(); area += b.width * b.height; } catch (e) { area += 1; }
      }
      return area < 1;
    }
    if ((m = cp.match(/^circle\(\s*([-\d.]+)(px|%)?/))) return parseFloat(m[1]) <= 0.5;
    if ((m = cp.match(/^ellipse\(\s*([-\d.]+)(px|%)?\s+([-\d.]+)(px|%)?/)))
      return parseFloat(m[1]) <= 0.5 || parseFloat(m[3]) <= 0.5;
    if ((m = cp.match(/^inset\(([^)]*?)(\s+round\b[^)]*)?\)/))) {
      const p = m[1].trim().split(/\s+/);
      const [t, r, b, l] = [p[0], p[1] || p[0], p[2] || p[0], p[3] || p[1] || p[0]];
      return len(t, h) + len(b, h) >= h - 0.5 || len(l, w) + len(r, w) >= w - 0.5;
    }
    if ((m = cp.match(/^polygon\(([^)]*)\)/))) {
      const pts = m[1].replace(/^\s*(nonzero|evenodd)\s*,/, '').split(',')
        .map(s => s.trim().split(/\s+/)).map(([x, y]) => [len(x, w), len(y, h)]);
      let area = 0;
      for (let i = 0; i < pts.length; i++) {
        const [x1, y1] = pts[i], [x2, y2] = pts[(i + 1) % pts.length];
        area += x1 * y2 - x2 * y1;
      }
      return Math.abs(area) / 2 < 1;
    }
    return false;
  }

  // clip: rect(top, right, bottom, left) — 절대 위치 요소에만 적용된다. auto 는 제한 없음.
  function clipRectZero(cs) {
    if (!/^(absolute|fixed)$/.test(cs.position)) return false;
    const m = (cs.clip || '').match(/^rect\(([^)]*)\)/);
    if (!m) return false;
    const v = m[1].split(/[\s,]+/).filter(Boolean).map(x => x === 'auto' ? null : parseFloat(x));
    if (v.length !== 4) return false;
    const [t, r, b, l] = v;
    return (r !== null && l !== null && r - l <= 0.5) || (b !== null && t !== null && b - t <= 0.5);
  }

  // filter: opacity(0.02) 처럼 필터로 흐리게 만든 정도
  function filterOpacity(f) {
    let o = 1;
    for (const m of (f || '').matchAll(/opacity\(\s*([\d.]+)(%)?\s*\)/g))
      o *= m[2] ? parseFloat(m[1]) / 100 : parseFloat(m[1]);
    return o;
  }

  // 조상의 overflow:hidden/clip 영역 밖으로 완전히 밀려났는가.
  // 절대 위치 요소는 위치가 지정된 조상(담는 블록)에서만 잘린다.
  function clippedByAncestor(el, box) {
    const pos = getComputedStyle(el).position;
    if (pos === 'fixed') return false;
    let escaping = pos === 'absolute';
    let cur = up(el);
    while (cur && cur.nodeType === 1 && cur !== document.documentElement && cur !== document.body) {
      const s = getComputedStyle(cur);
      const positioned = s.position !== 'static' || s.transform !== 'none';
      if (!(escaping && !positioned)) {
        const cx = /hidden|clip/.test(s.overflowX), cy = /hidden|clip/.test(s.overflowY);
        if (cx || cy) {
          const a = cur.getBoundingClientRect();
          const w = cx ? Math.min(box.right, a.right) - Math.max(box.left, a.left) : 1e9;
          const h = cy ? Math.min(box.bottom, a.bottom) - Math.max(box.top, a.top) : 1e9;
          if (w <= 1 || h <= 1) return true;
        }
        if (escaping && positioned) escaping = false;
      }
      if (s.position === 'fixed') return false;
      if (s.position === 'absolute') escaping = true;
      cur = up(cur);
    }
    return false;
  }

"""
