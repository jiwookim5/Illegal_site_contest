"""브라우저 안에서 실행되는 추출 스크립트.

페이지당 한 번만 호출해서 텍스트를 가진 요소 전체의 스타일 정보를 한꺼번에 가져온다.
왕복을 줄여야 검출 시간 배점(20점)을 지킬 수 있다. 유일성이 검증된 CSS 선택자는
광고로 판정된 글에만 필요하므로 판정 뒤 한 번 더 불러 만든다 (findings.NODE_SELECTORS).

일반 텍스트 노드 외에 ::before/::after content 와 Shadow DOM 내부도 훑는다.
선택자로 지목할 수 없는 영역(가상 요소·섀도 내부)은 호스트 요소를 위치로 보고한다.

숨긴 상자 안에서 <span>안전</span><span>놀이터</span> 처럼 광고를 여러 요소로 쪼개면
조각마다 점수가 모자라 빠진다. 그래서 가장 바깥 숨김 상자 단위로 조각을 합친 글도 함께 돌려준다
(parts: 합친 조각의 번호). 직접 붙은 인라인 조각은 한 문장으로 보고한다.
독립 링크·문단은 개별 검출을 우선하고, 미검출 조각만 합친 글로 보완한다(findings.py).
"""

from visibility_js import VISIBILITY_HELPERS
from selector_js import BUILD_SELECTOR
from context_js import LOCAL_CONTEXT

EXTRACT = r"""
() => {
  const OFFSCREEN_LIMIT = -1000;
  // 화면에 글자로 나타나지 않는 태그. 스크립트 소스를 본문으로 오인하면 오탐이 쏟아진다.
  const NON_TEXT = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'TITLE', 'META', 'LINK']);
  const out = [];
  const els = [];     // out[i] 가 요소 자신의 글자일 때 그 요소 (가상 요소·섀도 내부는 null)
  // 선택자는 문서를 여러 번 검색하므로 비싸다 (글이 많은 페이지에서 추출 시간의 절반 이상).
  // 여기서는 selector 를 비워 두고 위치로 보고할 요소만 targets[i] 에 남긴다.
  // findings.py 가 광고로 판정한 글의 선택자만 NODE_SELECTORS 로 만든다. 섀도 내부는 호스트 선택자를 바로 쓴다.
  const targets = [];

  // 요강 표기 규칙에 맞는 선택자를 만들되, 반드시 유일해야 한다 (selector_js.py).
  BUILD_SELECTOR

  function parseRGB(v) {
    const m = (v || '').match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(',').map(x => parseFloat(x.trim()));
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  }

  // Only a single gradient with every stop transparent is provably empty.
  // Partial gradients and external masks need pixel interpretation.
  function emptyMask(cs) {
    const mask = cs.maskImage || cs.webkitMaskImage || 'none';
    if (!/^(?:linear|radial|conic)-gradient\(/.test(mask) || /\),\s*(?:url|.*gradient)\(/.test(mask)) return false;
    const stops = mask.match(/rgba?\([^)]*\)/g) || [];
    return stops.length >= 2 && stops.every(s => parseRGB(s)?.a === 0);
  }
  const up = (cur) => cur.parentElement || (cur.getRootNode() && cur.getRootNode().host);

  // 글자 뒤에 칠해지는 바탕색들. 그림 바탕(url)이면 색을 알 수 없으므로 null 을 돌려준다
  // (어두운 배너 그림 위 흰 글씨를 '흰 바탕 흰 글씨'로 오판하지 않기 위함).
  // 그라데이션은 그 안의 색들을 모두 돌려주고, 판정은 어느 색과도 구분되지 않을 때만 투명으로 본다.
  // html·body 에 깐 무늬 그림은 바탕색이 함께 지정돼 있으면 그 색으로 본다.
  // 요소마다 조상을 끝까지 다시 오르지 않도록 요소별 결과를 기억한다 (추출 중에는 DOM 이 바뀌지 않는다)
  const bgCache = new Map();

  // 바탕색 말고도 글자 뒤를 칠하는 것들. 조상의 바탕색만 보면 '검은 상자 위 흰 글씨'로 읽히지만
  // 실제로는 흰 판 위에 흰 글씨인 경우다.
  //  - 상자를 다 덮는 안쪽 그림자 (box-shadow: inset 0 0 0 999px #fff)
  //  - 상자를 덮는 위치 지정 ::before/::after 바탕 (부모의 가상 요소로 깐 흰 판)
  //  - 앞서 놓인 위치 지정 형제 요소 (position:absolute 로 깐 흰 판)
  const opaque = (c) => c && c.a > 0.9 ? c : null;
  function insetCover(cs, rect) {
    if (!cs.boxShadow || cs.boxShadow === 'none' || !/inset/.test(cs.boxShadow)) return null;
    for (const sh of cs.boxShadow.split(/,(?![^(]*\))/)) {
      if (!/inset/.test(sh)) continue;
      const nums = (sh.replace(/rgba?\([^)]*\)/, '').match(/-?[\d.]+px/g) || []).map(parseFloat);
      const spread = nums.length >= 4 ? nums[3] : 0;
      const c = opaque(parseRGB(sh));
      if (c && spread >= Math.min(rect.width, rect.height) / 2) return c;
    }
    return null;
  }
  function pseudoCover(el, rect) {
    for (const pe of ['::after', '::before']) {        // ::after 가 위에 그려진다
      let s;
      try { s = getComputedStyle(el, pe); } catch (e) { continue; }
      if (!s || s.content === 'none' || s.display === 'none' || !/^(absolute|fixed)$/.test(s.position)) continue;
      const c = opaque(parseRGB(s.backgroundColor));
      if (c && parseFloat(s.width) >= rect.width - 1 && parseFloat(s.height) >= rect.height - 1) return c;
    }
    return null;
  }
  // 부모마다 한 번: 위치 지정·불투명 바탕을 가진 자식들 (큰 표에서 형제를 거듭 훑지 않도록)
  const layerCache = new Map();
  function layersOf(parent) {
    let v = layerCache.get(parent);
    if (v) return v;
    v = [];
    for (const k of parent.children) {
      const s = getComputedStyle(k);
      if (!/^(absolute|fixed)$/.test(s.position) || s.visibility !== 'visible' || parseFloat(s.opacity) < 0.9) continue;
      const c = opaque(parseRGB(s.backgroundColor));
      if (c) v.push({ el: k, c, rect: k.getBoundingClientRect() });
    }
    layerCache.set(parent, v);
    return v;
  }
  function siblingCover(el, rect) {
    const parent = el.parentElement;
    if (!parent) return null;
    const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
    let hit = null;
    for (const l of layersOf(parent)) {
      if (l.el === el) break;                         // 뒤에 놓인 형제는 글 위에 그려진다 (덮으면 어차피 안 보인다)
      if (l.rect.left <= cx && cx <= l.rect.right && l.rect.top <= cy && cy <= l.rect.bottom) hit = l.c;
    }
    return hit;
  }

  function effectiveBgs(el) {
    if (!el || el.nodeType !== 1) return [{ r: 255, g: 255, b: 255, a: 1 }];
    if (bgCache.has(el)) return bgCache.get(el);
    const cs = getComputedStyle(el);
    const c = parseRGB(cs.backgroundColor);
    const img = cs.backgroundImage || 'none';
    const rect = el.getBoundingClientRect();
    const cover = rect.width > 0 && rect.height > 0 &&
                  (pseudoCover(el, rect) || insetCover(cs, rect));
    let r;
    if (cover) {
      r = [cover];
    } else if (img !== 'none' && /url\(/.test(img)) {
      const page = el === document.body || el === document.documentElement;
      r = page && c && c.a > 0.1 ? [c] : null;
    } else {
      const stops = img === 'none' ? [] :
        (img.match(/rgba?\([^)]+\)/g) || []).map(parseRGB).filter((x) => x && x.a > 0.1);
      const under = !stops.length && !(c && c.a > 0.1) && rect.width > 0 ? siblingCover(el, rect) : null;
      r = stops.length ? stops : c && c.a > 0.1 ? [c] : under ? [under] : effectiveBgs(up(el));
    }
    bgCache.set(el, r);
    return r;
  }

  function luminance(c) {
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  }

  function ratio(a, b) {
    const l1 = luminance(a), l2 = luminance(b);
    return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
  }
  const colorsIn = (v) => (v || '').match(/rgba?\([^)]+\)/g) || [];

  // 글자색이 투명해도 다른 방법으로 글자 모양을 칠하면 화면에 보인다.
  // 그라데이션 제목(background-clip:text), 글자 그림자(text-shadow), 외곽선 글씨(-webkit-text-stroke).
  // 칠한 색이 글자 뒤 바탕과 구분될 때만 보이는 글로 본다 (바탕과 같은 색으로 칠한 숨김은 그대로 잡는다).
  function paintedOtherwise(el, cs) {
    const differs = (colors, backs) => !backs || colors.some(c => backs.some(b => ratio(c, b) >= 1.2));
    const clip = cs.webkitBackgroundClip || cs.backgroundClip || '';
    const img = cs.backgroundImage || 'none';
    if (/text/.test(clip) && img !== 'none') {
      if (/url\(/.test(img)) return true;
      const stops = colorsIn(img).map(parseRGB).filter(c => c && c.a > 0.1);
      // 이 요소의 바탕은 글자 안에만 칠해지므로 글자 뒤 바탕은 부모 쪽에서 찾는다
      if (stops.length && differs(stops, effectiveBgs(up(el)))) return true;
    }
    const bgs = effectiveBgs(el);
    if (cs.textShadow && cs.textShadow !== 'none') {
      const shadows = colorsIn(cs.textShadow).map(parseRGB).filter(c => c && c.a > 0.1);
      if (shadows.length && differs(shadows, bgs)) return true;
    }
    if (el instanceof SVGElement && cs.stroke && cs.stroke !== 'none' && (parseFloat(cs.strokeWidth) || 0) >= 0.5) {
      const s = parseRGB(cs.stroke);
      if (s && s.a * (parseFloat(cs.strokeOpacity) || 0) > 0.1 && differs([s], bgs)) return true;
    }
    if ((parseFloat(cs.webkitTextStrokeWidth) || 0) >= 0.5) {
      const stroke = parseRGB(cs.webkitTextStrokeColor);
      if (stroke && stroke.a > 0.1 && differs([stroke], bgs)) return true;
    }
    return false;
  }

  // 길이 값 하나를 px 로. 퍼센트는 기준 길이(base)에 대한 비율.
  VISIBILITY_HELPERS

  // 조상 사슬에서 결정되는 은닉 (섀도 호스트도 거슬러 올라간다). 부모의 결과에 자신을 더해 기억한다
  const NOT_HIDDEN = { displayNone: false, opacityZero: false, clipPath: false, alpha: 1, cvHidden: false, fixed: false, detailsClosed: false };
  const inhCache = new Map();
  function inherited(el) {
    if (!el || el.nodeType !== 1) return NOT_HIDDEN;
    let v = inhCache.get(el);
    if (v) return v;
    const p = inherited(up(el));
    const s = getComputedStyle(el);
    // 투명도는 조상과 곱해진다 (부모 0.2 × 자식 0.1 = 0.02). 하나씩은 기준을 넘어도 곱이 0에 가까우면 은닉이다
    const alpha = p.alpha * (parseFloat(s.opacity) || 0) * filterOpacity(s.filter);
    v = {
      displayNone: p.displayNone || s.display === 'none',
      // 0.02 처럼 0에 가까운 값도 은닉이다. filter:opacity() 도 같은 효과다.
      opacityZero: p.opacityZero || alpha <= 0.05,
      maskZero: p.maskZero || emptyMask(s),
      alpha,
      // content-visibility:hidden (hidden="until-found" 도 같다) 은 안쪽 글을 그리지 않는다
      cvHidden: p.cvHidden || s.contentVisibility === 'hidden',
      // 닫힌 <details> 의 본문(제목 summary 말고)은 그려지지 않는다. 크기는 브라우저가 계산하는 때에 따라
      // 0 으로도, 펼친 크기로도 나와서 좌표로는 가릴 수 없으니 구조로 본다
      detailsClosed: p.detailsClosed || (!!el.parentElement && el.parentElement.tagName === 'DETAILS' &&
                                         !el.parentElement.open && el.tagName !== 'SUMMARY'),
      fixed: p.fixed || s.position === 'fixed',
      clipPath: p.clipPath || (!!s.clipPath && s.clipPath !== 'none' &&
                               clipPathZero(s.clipPath, el.getBoundingClientRect())),
    };
    inhCache.set(el, v);
    return v;
  }

  // 글자가 실제로 칠해지는 자리. 들여쓰기·줄바꿈 금지로 상자 밖에 나간 글자도 잡으려면
  // 요소 상자가 아니라 텍스트 노드의 범위를 재야 한다.
  function textRect(el) {
    let box = null;
    for (const n of el.childNodes) {
      if (n.nodeType !== 3 || !n.nodeValue.trim()) continue;
      const range = document.createRange();
      range.selectNodeContents(n);
      const r = range.getBoundingClientRect();
      if (!r.width && !r.height) continue;
      box = box ? { left: Math.min(box.left, r.left), top: Math.min(box.top, r.top),
                    right: Math.max(box.right, r.right), bottom: Math.max(box.bottom, r.bottom) }
                : { left: r.left, top: r.top, right: r.right, bottom: r.bottom };
    }
    return box;
  }

  // 가로 스크롤이 막혀 있으면 화면 오른쪽 밖은 볼 방법이 없다
  const rootX = [getComputedStyle(document.documentElement).overflowX,
                 document.body ? getComputedStyle(document.body).overflowX : 'visible'];
  const noScrollX = rootX.some(v => /hidden|clip/.test(v));

  // 문서 뷰어는 쪽 그림 위에 글자 크기 0(또는 투명) 글자층을 겹쳐 고르고 찾을 수 있게 한다.
  // 그 글은 그림으로 화면에 보이므로 숨긴 글이 아니라 보이는 글로 판정한다 (2026-10-19 gb.go.kr 시냅 뷰어의
  // 채용 신체검사서 '마약류 검사' 항목을 화면 밖 은닉 광고로 잘못 봄). 알려진 뷰어의 구조와 그 뷰어
  // 스크립트가 함께 있을 때만 인정한다. 이미지를 끄고 점검하므로 그림 크기는 보지 않는다
  const viewerScript = (pattern) => [...document.scripts].some(s => pattern.test(s.src || ''));
  const SYNAP = viewerScript(/synap/i);
  const PDFJS = !!(window.PDFViewerApplication || document.getElementById('viewerContainer'));
  function documentTextLayer(el) {
    if (SYNAP) {
      const page = el.closest('.contents-page[id^="page-area"]');
      if (page && page.querySelector(':scope > img.contents-page__img')) return true;
    }
    if (PDFJS) {
      const page = el.closest('.textLayer') && el.closest('.page[data-page-number]');
      if (page && page.querySelector('canvas')) return true;
    }
    return false;
  }

  function styleVerdict(el, cs, inh, pseudo) {
    const rect = el.getBoundingClientRect();
    // transform 으로 줄였으면 화면에 그려지는 글자 크기는 그만큼 작다
    const scale = el.offsetHeight > 0 ? rect.height / el.offsetHeight : 1;
    const fontSize = (parseFloat(cs.fontSize) || 0) * Math.min(scale, 1);
    // -webkit-text-fill-color 가 있으면 글자는 color 가 아니라 그 색으로 칠해진다.
    // SVG 글자는 color 가 아니라 fill 로 칠해진다 (fill="none"·fill-opacity="0" 이면 칠하지 않는다)
    let color = parseRGB(cs.webkitTextFillColor) || parseRGB(cs.color) || { r: 0, g: 0, b: 0, a: 1 };
    if (el instanceof SVGElement) {
      const f = cs.fill === 'none' ? { r: 0, g: 0, b: 0, a: 0 } : parseRGB(cs.fill);
      if (f) color = { ...f, a: f.a * (cs.fillOpacity === '' ? 1 : parseFloat(cs.fillOpacity)) };
    }
    const bgs = effectiveBgs(el);
    let colorAlphaZero = color.a === 0;
    // 바탕색을 알 수 없으면(그림 바탕) 대비비로는 판정하지 않는다
    let contrast = 21;
    if (bgs) {
      contrast = 0;
      for (const bg of bgs) {
        const blend = (fg, back) => cs.mixBlendMode === 'screen' ? 255 - (255 - fg) * (255 - back) / 255
          : cs.mixBlendMode === 'multiply' ? fg * back / 255 : fg;
        const blended = {
          r: color.a * blend(color.r, bg.r) + (1 - color.a) * bg.r,
          g: color.a * blend(color.g, bg.g) + (1 - color.a) * bg.g,
          b: color.a * blend(color.b, bg.b) + (1 - color.a) * bg.b,
        };
        contrast = Math.max(contrast, ratio(blended, bg));
      }
    }
    if ((colorAlphaZero || contrast < 1.2) && paintedOtherwise(el, cs)) {
      colorAlphaZero = false;
      contrast = 21;
    }

    const indent = parseFloat(cs.textIndent) || 0;
    const indented = indent <= -500;
    const clipped = clipRectZero(cs) || inh.clipPath;
    // visibility 는 상속되지만 자식이 visible 로 되돌릴 수 있어, 조상이 아니라 자신의 계산값을 본다
    const visHidden = cs.visibility === 'hidden' || cs.visibility === 'collapse';

    const box = (!pseudo && textRect(el)) || rect;
    const sx = window.scrollX, sy = window.scrollY;
    // 크기가 0 인 상자(렌더링되지 않은 영역)는 좌표가 (0,0) 으로 나오므로 화면 밖 판정에서 뺀다
    const hasBox = box.right - box.left > 0 || box.bottom - box.top > 0;
    const movedOut = !inh.displayNone && hasBox && (
      box.right + sx <= 0 || box.bottom + sy <= 0 ||                  // 문서 왼쪽·위쪽 밖
      box.left < OFFSCREEN_LIMIT || box.top < OFFSCREEN_LIMIT ||
      box.left + sx >= innerWidth + (noScrollX ? 0 : 1000));          // 오른쪽 밖
    // Explicit large negative bottom offsets move text far away from its own
    // containing block. Ordinary content below the viewport is still readable.
    const container = el.offsetParent;
    const displacedBelow = !inh.displayNone && hasBox && cs.position === 'absolute' &&
      parseFloat(cs.bottom) < OFFSCREEN_LIMIT && container &&
      box.top - container.getBoundingClientRect().bottom > Math.max(1000, innerHeight * 2);
    const overflowHidden = !inh.displayNone && !movedOut && clippedByAncestor(el, box);
    const collapsed = !inh.displayNone && (
      (rect.width <= 1 && rect.height <= 1) ||
      ((rect.width <= 1 || rect.height <= 1) && cs.overflow !== 'visible'));
    // transform 으로 한 방향만 0 으로 눌렀다 (rotateY(90deg)·scaleX(0)). offsetWidth 는 transform 전 크기다
    const flattened = !inh.displayNone && !collapsed && el.offsetWidth > 1 && el.offsetHeight > 1 &&
                      (rect.width <= 0.5 || rect.height <= 0.5);
    // 화면에 고정된 요소는 스크롤해도 움직이지 않으므로 화면 밖(아래쪽 포함)에 두면 볼 수 없다
    const fixedOut = !inh.displayNone && inh.fixed && hasBox && !movedOut && (
      box.top >= innerHeight || box.left >= innerWidth || box.bottom <= 0 || box.right <= 0);
    // 자기 자신에 overflow:hidden 을 걸고 글을 상자 밖으로 민다 (text-indent:100%, padding-top 으로 밀어내기)
    let selfOut = false;
    if (!pseudo && !inh.displayNone && !movedOut && /hidden|clip/.test(cs.overflowX + cs.overflowY)) {
      const tb = textRect(el);
      if (tb) {
        const a = el.getBoundingClientRect();
        const w = Math.min(tb.right, a.right) - Math.max(tb.left, a.left);
        const h = Math.min(tb.bottom, a.bottom) - Math.max(tb.top, a.top);
        selfOut = w <= 1 || h <= 1;
      }
    }

    const transparent = inh.opacityZero || inh.maskZero || colorAlphaZero || contrast < 1.2;
    const offscreen = inh.displayNone || visHidden || fontSize <= 1 ||
                      movedOut || collapsed || indented || clipped || overflowHidden ||
                      inh.cvHidden || inh.detailsClosed || flattened || fixedOut || selfOut || displacedBelow;

    const reasons = [];
    if (inh.opacityZero) reasons.push('opacity:0');
    if (inh.maskZero) reasons.push('완전히 투명한 CSS mask');
    if (colorAlphaZero) reasons.push(parseRGB(cs.webkitTextFillColor) && parseRGB(cs.webkitTextFillColor).a === 0
                                     ? '-webkit-text-fill-color:transparent' : 'color:transparent');
    if (!inh.opacityZero && !colorAlphaZero && contrast < 1.2) reasons.push('배경 대비비 ' + contrast.toFixed(2));
    if (inh.displayNone) reasons.push('display:none');
    if (visHidden) reasons.push('visibility:hidden');
    if (fontSize <= 1) reasons.push(scale < 0.99 ? `transform 축소 후 글자 ${fontSize.toFixed(2)}px`
                                                 : 'font-size:' + cs.fontSize);
    if (movedOut) reasons.push('화면 밖 좌표 left:' + Math.round(box.left) + 'px, top:' + Math.round(box.top) + 'px');
    if (indented) reasons.push('text-indent:' + cs.textIndent);
    if (clipped) reasons.push('clip 영역 0');
    if (overflowHidden) reasons.push('상위 요소 overflow:hidden 영역 밖');
    if (collapsed) reasons.push('크기 ' + Math.round(rect.width) + 'x' + Math.round(rect.height));
    if (inh.cvHidden) reasons.push('content-visibility:hidden');
    if (inh.detailsClosed) reasons.push('닫힌 <details> 안');
    if (flattened) reasons.push('transform 으로 한 방향 크기 0 (' + Math.round(rect.width) + 'x' + Math.round(rect.height) + ')');
    if (fixedOut) reasons.push('position:fixed 로 화면 밖 고정 (top:' + Math.round(box.top) + 'px)');
    if (selfOut) reasons.push('자기 overflow:hidden 상자 밖으로 글을 밂');
    if (displacedBelow) reasons.push('큰 음수 bottom으로 담는 상자 아래 멀리 이동: ' + cs.bottom);

    // 뷰어 글자층의 작은 글자·투명 글자는 쪽 그림으로 보인다. display:none·화면 밖 이동처럼
    // 그림과 상관없이 감춘 경우는 그대로 숨김으로 본다
    if ((transparent || offscreen) && !inh.displayNone && !visHidden && !movedOut && !fixedOut &&
        !displacedBelow && documentTextLayer(el))
      return { transparent: false, offscreen: false, reasons: [], rect, documentLayer: true };

    return { transparent, offscreen, reasons, rect };
  }

  // 다른 요소에 완전히 덮여 보이지 않는가 (요강 주요 4종 밖이라 추가 유형으로 다룬다)
  function isOccluded(el, rect) {
    if (rect.width < 3 || rect.height < 3) return false;
    const cx = rect.left + rect.width / 2, cy = rect.top + rect.height / 2;
    if (cx < 0 || cy < 0 || cx > innerWidth || cy > innerHeight) return false;
    let top;
    try { top = document.elementFromPoint(cx, cy); } catch (e) { return false; }
    if (!top || top === el) return false;
    return !el.contains(top) && !top.contains(el);
  }

  function readable(el, inactivePanel = null) {
    if (!el) return false;
    const v = styleVerdict(el, getComputedStyle(el), inherited(el));
    if (v.transparent || isOccluded(el, v.rect)) return false;
    if (!v.offscreen) return true;
    if (!inactivePanel || !inactivePanel.contains(el) ||
        v.reasons.some(reason => reason !== 'display:none')) return false;
    for (let cur = el; cur && cur !== inactivePanel; cur = up(cur)) {
      if (getComputedStyle(cur).display === 'none') return false;
    }
    return true;
  }
  const localContext = LOCAL_CONTEXT;
  // EXTRACT_EXTRA runs immediately after this extraction in the same JS call.
  window.__hwonhiReadable = readable;
  window.__hwonhiContext = (el, label = null) => localContext(el, readable, buildSelector, label);

  const fontFaces = new Map();
  const familyKey = name => name.trim().replace(/^["']|["']$/g, '').toLowerCase();
  function collectFaces(sheet, seen = new Set()) {
    if (seen.has(sheet)) return;
    seen.add(sheet);
    let rules;
    try { rules = sheet.cssRules; } catch (_) { return; }
    for (const rule of rules) {
      if (rule.type === CSSRule.FONT_FACE_RULE) {
        const family = familyKey(rule.style.getPropertyValue('font-family'));
        const src = rule.style.getPropertyValue('src');
        const urls = Array.from(src.matchAll(/url\(["']?([^"')]+)["']?\)/g), m => {
          try { return new URL(m[1], sheet.href || document.baseURI).href; } catch (_) { return ''; }
        }).filter(Boolean);
        const weight = rule.style.getPropertyValue('font-weight') || 'normal';
        const style = rule.style.getPropertyValue('font-style') || 'normal';
        // Only font faces actually loaded by the browser can explain displayed text.
        const loaded = Array.from(document.fonts).some(f => f.status === 'loaded' &&
          familyKey(f.family) === family && f.weight === weight && f.style === style);
        if (loaded) fontFaces.set(family, [...(fontFaces.get(family) || []), { urls, weight, style }]);
      } else if (rule.styleSheet) collectFaces(rule.styleSheet, seen);
    }
  }
  for (const sheet of document.styleSheets) collectFaces(sheet);
  function scanRoot(root, hostSelector) {
    // body 자신도 본다. 태그 없이 body 바로 아래 넣은 글('<body>…<p>공지</p>광고 글</body>')은
    // 하위 요소만 돌면 어느 요소의 글에도 들지 않는다
    const all = root.nodeType === 1 ? [root, ...root.querySelectorAll('*')] : root.querySelectorAll('*');
    for (const el of all) {
      if (NON_TEXT.has(el.tagName)) continue;
      const shadow = el.shadowRoot || window.__hwonhiShadowRootOf?.(el);
      if (shadow) scanRoot(shadow, hostSelector || buildSelector(el));
      const cs = getComputedStyle(el);
      const inh = inherited(el);
      // 항목을 만드는 객체 안에서 out.push 직전에 부르므로 out.length 가 그 항목의 번호다
      const sel = () => {
        if (!hostSelector) targets[out.length] = el;
        return hostSelector;
      };

      // 1) 요소가 직접 들고 있는 텍스트 (부모와 중복 보고를 막는다)
      let own = '';
      for (const n of el.childNodes) if (n.nodeType === 3) own += n.nodeValue;
      let visual = null;
      if (cs.unicodeBidi.includes('bidi-override') && cs.direction === 'rtl' && !el.children.length)
        visual = Array.from(own).reverse().join('');
      // Character fragments in a single left-to-right flex row follow CSS order.
      const children = Array.from(el.children);
      if (/flex/.test(cs.display) && cs.flexDirection === 'row' && cs.direction === 'ltr' &&
          children.length > 1 && !own.trim() &&
          children.every(c => !c.children.length && Array.from(c.textContent).length === 1)) {
        const positions = children.map(c => ({ c, r: c.getBoundingClientRect() }));
        if (positions.every(p => (p.r.width > 0 || !p.c.textContent.trim()) && p.r.height > 0) &&
            positions.every(p => Math.abs(p.r.top - positions[0].r.top) < 2))
          visual = children.sort((a, b) => Number(getComputedStyle(a).order) - Number(getComputedStyle(b).order))
                           .map(c => c.textContent).join('');
      }
      if (visual && visual !== el.textContent) {
        const v = styleVerdict(el, cs, inh);
        out.push({ text: visual, selector: sel(), transparent: v.transparent, offscreen: v.offscreen,
          occluded: false, reasons: v.reasons.concat(['CSS 표시 순서 복원']), visualOrder: true,
          context: hostSelector ? null : window.__hwonhiContext(el) });
        els.push(null);
      }
      if (el.tagName === 'CANVAS') {
        const text = window.__hwonhiCanvasText?.(el);
        if (text) {
          const v = styleVerdict(el, cs, inh);
          out.push({ text, selector: sel(), transparent: v.transparent, offscreen: v.offscreen,
            occluded: false, reasons: v.reasons, canvasText: true });
          els.push(null);
        }
      }
      if (own.trim()) {
        const v = styleVerdict(el, cs, inh);
        const occluded = !v.transparent && !v.offscreen && !hostSelector && isOccluded(el, v.rect);
        out.push({
          text: own, selector: sel(), transparent: v.transparent, offscreen: v.offscreen,
          fontSources: cs.fontFamily.split(',').flatMap(f => fontFaces.get(familyKey(f)) || [])
            .filter(f => f.style === cs.fontStyle && (f.weight === cs.fontWeight ||
              f.weight === 'normal' && cs.fontWeight === '400')) .flatMap(f => f.urls),
          occluded, reasons: v.reasons.concat(hostSelector ? ['Shadow DOM 내부'] : []),
          context: hostSelector ? null : window.__hwonhiContext(el),
          hiddenLinkPeers: v.offscreen && el.tagName === 'A' && el.parentElement &&
            getComputedStyle(el.parentElement).display === 'none'
            ? Array.from(el.parentElement.children).filter(p => p !== el && p.tagName === 'A')
                .slice(0, 20).map(p => p.textContent.slice(0, 1000)) : [],
        });
        els.push(hostSelector ? null : el);
      }

      // 2) 가상 요소로 끼워 넣은 문자열
      for (const pe of ['::before', '::after']) {
        let cs2;
        try { cs2 = getComputedStyle(el, pe); } catch (e) { continue; }
        const raw = cs2 && cs2.content;
        if (!raw || raw === 'none' || raw === 'normal') continue;
        const m = raw.match(/^"([\s\S]*)"$/) || raw.match(/^'([\s\S]*)'$/);
        if (!m || !m[1].trim()) continue;
        const v = styleVerdict(el, cs2, inh, true);
        out.push({
          text: m[1], selector: sel(), transparent: v.transparent, offscreen: v.offscreen,
          occluded: false, reasons: v.reasons.concat([pe + ' content 삽입']),
          generated: pe,
        });
        els.push(null);
      }
    }
  }

  if (!document.body) throw new Error("본문이 준비되지 않았거나 이동 중입니다");
  scanRoot(document.body, null);

  // 3) 쪼갠 글 합치기: 숨긴 조각마다 위로 올라가며 숨김이 이어지는 가장 바깥 상자를 찾는다
  const verdicts = new Map();
  const hiddenBox = (el) => {
    if (!verdicts.has(el)) {
      let v = null;
      try { v = styleVerdict(el, getComputedStyle(el), inherited(el)); } catch (e) {}
      verdicts.set(el, v && (v.transparent || v.offscreen) ? v : null);
    }
    return verdicts.get(el);
  };
  const indexOf = new Map();
  els.forEach((el, i) => { if (el) indexOf.set(el, i); });

  // 숨긴 문장 안의 꾸밈 태그(<p>먹튀검증 <b>안전놀이터</b> 텔레그램</p>)는 문장의 일부다.
  // 같은 숨김이 걸린 꾸밈 태그에 문장 번호(sp)를 달고, 문장에는 꾸밈 태그 글자까지 넣은 전체 글(full)을 단다.
  // 둘 다 광고로 잡히면 scan.py 가 문장 한 건으로 합친다 (따로 세면 한 광고가 두 건이 되고 근거 문구가 깨진다).
  const INLINE = new Set(['A', 'B', 'STRONG', 'EM', 'I', 'U', 'S', 'SPAN', 'FONT', 'MARK', 'SMALL', 'BIG',
                          'SUB', 'SUP', 'CODE', 'ABBR', 'CITE', 'Q', 'INS', 'DEL', 'TIME', 'LABEL']);
  const sameHide = (i, j) => out[i].transparent === out[j].transparent && out[i].offscreen === out[j].offscreen;
  const sentenceOwners = new Set();
  for (let i = 0; i < els.length; i++) {
    const el = els[i];
    if (!el || !(out[i].transparent || out[i].offscreen) || !INLINE.has(el.tagName)) continue;
    let cur = el.parentElement;
    while (cur && !indexOf.has(cur) && INLINE.has(cur.tagName)) cur = cur.parentElement;
    if (!cur || !indexOf.has(cur)) continue;
    const p = indexOf.get(cur);
    if (!sameHide(i, p)) continue;
    out[i].sp = p;
    sentenceOwners.add(p);
  }
  const sentence = (node, p) => {
    let text = '';
    for (const n of node.childNodes) {
      if (n.nodeType === 3) { text += n.nodeValue; continue; }
      if (n.nodeType !== 1 || !INLINE.has(n.tagName)) continue;
      const j = indexOf.get(n);
      if (j === undefined || out[j].sp === p) text += sentence(n, p);
    }
    return text;
  };
  for (const p of sentenceOwners) out[p].full = sentence(els[p], p);
  const groups = new Map();
  const n0 = out.length;
  for (let i = 0; i < n0; i++) {
    const el = els[i];
    if (!el || !(out[i].transparent || out[i].offscreen)) continue;
    let root = el;
    while (root.parentElement && root.parentElement !== document.body && hiddenBox(root.parentElement))
      root = root.parentElement;
    if (root === el) continue;
    if (!groups.has(root)) groups.set(root, new Set(indexOf.has(root) ? [indexOf.get(root)] : []));
    groups.get(root).add(i);
  }
  for (const [root, set] of groups) {
    const parts = [...set].sort((a, b) => a - b);
    if (parts.length < 2) continue;
    const v = hiddenBox(root);
    if (!v) continue;
    targets[out.length] = root;
    out.push({
      text: parts.map((i) => out[i].text.trim()).join(' '), selector: null,
      transparent: v.transparent, offscreen: v.offscreen, occluded: false,
      reasons: v.reasons.concat(['여러 요소로 쪼갠 글을 합쳐 판정']), parts,
      // A local uninterrupted inline sentence owns its fragments. Independent
      // links, paragraphs, lists and nested containers remain separate findings.
      sentenceGroup: !indexOf.has(root) && parts.every(i => els[i]?.parentElement === root) &&
        Array.from(root.children).every(c => INLINE.has(c.tagName) && c.tagName !== 'A' &&
          !c.children.length && (getComputedStyle(c).display === 'inline' ||
                                getComputedStyle(c).display === 'none')),

    });
  }
  window.__hwonhiTargets = targets;
  return out;
}
"""

EXTRACT = EXTRACT.replace("BUILD_SELECTOR", BUILD_SELECTOR.strip(), 1)
EXTRACT = EXTRACT.replace("LOCAL_CONTEXT", LOCAL_CONTEXT.strip(), 1)

EXTRACT = EXTRACT.replace("VISIBILITY_HELPERS", VISIBILITY_HELPERS.strip(), 1)
