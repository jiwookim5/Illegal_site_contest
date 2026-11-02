"""숨겨진 광고를 눈에 보이게 만들어 증거 화면을 남긴다.

담당자가 겪는 실제 어려움은 '광고가 있다는데 화면에서 안 보인다'는 점이다.
은닉 스타일을 일시적으로 풀고 테두리를 둘러 촬영해 두면 조치 근거로 바로 쓸 수 있다.
"""
import hashlib
import os

# Keep DOM references, including ancestors without a style attribute. Restoring
# cssText alone would leave style="" behind and can change attribute selectors.
SNAPSHOT_JS = """el => {
  const nodes = [];
  for (let n = el; n; n = n.parentElement)
    nodes.push({el:n, style:n.getAttribute('style'), x:n.scrollLeft, y:n.scrollTop});
  return {nodes, x:scrollX, y:scrollY};
}"""
RESTORE_JS = """state => {
  for (const n of state.nodes) {
    // Synchronize Chromium's lazy CSSOM attribute before removing it.
    if (n.style === null) { n.el.setAttribute('style', ''); n.el.removeAttribute('style'); }
    else n.el.setAttribute('style', n.style);
  }
  for (const n of state.nodes) { n.el.scrollLeft = n.x; n.el.scrollTop = n.y; }
  scrollTo(state.x, state.y);
}"""

# 요소와 그 조상에 걸린 은닉 스타일을 모두 무력화한다.
REVEAL_JS = r"""
(el) => {
  // 스타일을 건드리기 전에 원본 HTML 을 먼저 확보한다.
  const original = el.outerHTML.slice(0, 4000);

  const force = (node, inline) => {
    const s = node.style;
    const cs = getComputedStyle(node);
    if (cs.display === 'none') s.setProperty('display', inline ? 'inline-block' : 'block', 'important');
    s.setProperty('visibility', 'visible', 'important');
    s.setProperty('opacity', '1', 'important');
    if (cs.position === 'absolute' || cs.position === 'fixed') {
      s.setProperty('position', 'static', 'important');
    }
    s.setProperty('left', 'auto', 'important');
    s.setProperty('top', 'auto', 'important');
    s.setProperty('text-indent', '0', 'important');
    s.setProperty('transform', 'none', 'important');
    s.setProperty('clip', 'auto', 'important');
    s.setProperty('clip-path', 'none', 'important');
    s.setProperty('overflow', 'visible', 'important');
    if (parseFloat(cs.height) <= 1) s.setProperty('height', 'auto', 'important');
    if (parseFloat(cs.width) <= 1) s.setProperty('width', 'auto', 'important');
    if (parseFloat(cs.fontSize) <= 1) s.setProperty('font-size', '15px', 'important');
  };

  const inline = ['SPAN', 'A', 'EM', 'STRONG', 'B', 'I', 'LABEL'].includes(el.tagName);
  force(el, inline);
  let cur = el.parentElement;
  while (cur && cur.nodeType === 1) { force(cur, false); cur = cur.parentElement; }

  // 검출된 요소 자체를 눈에 띄게 표시한다.
  el.style.setProperty('color', '#111111', 'important');
  el.style.setProperty('background-color', '#fdeced', 'important');
  el.style.setProperty('outline', '3px solid #d7141e', 'important');
  el.style.setProperty('outline-offset', '2px', 'important');
  el.style.setProperty('padding', '4px 6px', 'important');
  el.scrollIntoView({ block: 'center', inline: 'nearest' });
  return original;
}
"""


def key_for(url, location):
    return hashlib.sha1(f"{url}|{location}".encode("utf-8")).hexdigest()[:16]


def capture(frame, selector, url, location, out_dir):
    """요소를 드러내 촬영하고 (파일명, 원본 HTML) 을 돌려준다.

    촬영에 실패해도 탐지 자체는 계속되어야 하므로 예외를 흘려보내지 않는다.
    """
    snapshot = None
    handle = None
    try:
        handle = frame.query_selector(selector)
        if handle is None:
            return None, None
        snapshot = handle.evaluate_handle(SNAPSHOT_JS)
        outer_html = handle.evaluate(REVEAL_JS)
        frame.page.wait_for_timeout(40)
        name = key_for(url, location) + ".png"
        os.makedirs(out_dir, exist_ok=True)
        handle.screenshot(path=os.path.join(out_dir, name), timeout=4000)
        return name, outer_html
    except Exception:
        return None, None
    finally:
        if snapshot is not None:
            try:
                snapshot.evaluate(RESTORE_JS)
            except Exception:
                pass  # A navigation/detachment can destroy the original document.
            finally:
                try:
                    snapshot.dispose()
                except Exception:
                    pass
        if handle is not None:
            try:
                handle.dispose()
            except Exception:
                pass
