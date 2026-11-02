"""탐지 시점의 페이지를 앱 안에서 다시 열어 보여준다.

원본 사이트를 iframe 으로 직접 불러오면 X-Frame-Options 로 막히고,
교차 출처라 검출 위치를 짚어줄 수도 없다. 그래서 탐지할 때 받아둔 HTML 을
우리 서버가 같은 출처로 내보내고, 그 안에서 요소를 표시한다.
"""
import json
import re
import secrets

# 스타일·이미지 같은 상대 경로 자원은 원본 사이트에서 그대로 불러온다.
BASE_TAG = '<base href="{url}">'

HIGHLIGHT = """
<style id="__ad_detector_style">
  .__ad_detector_hit {
    outline: 3px solid #d7141e !important;
    outline-offset: 2px !important;
    background-color: #fdeced !important;
    color: #111111 !important;
  }
  #__ad_detector_bar {
    position: fixed; left: 0; right: 0; top: 0; z-index: 2147483647;
    background: #111111; color: #fff; font: 600 13px/1.5 system-ui, sans-serif;
    padding: 8px 14px; box-shadow: 0 2px 8px rgba(0,0,0,.25);
  }
  body { margin-top: 42px !important; }
</style>
<script id="__ad_detector_script" nonce="__NONCE__">
(function () {
  var SEL = __SELECTOR__;
  var bar = document.createElement('div');
  bar.id = '__ad_detector_bar';
  document.addEventListener('DOMContentLoaded', place);
  if (document.readyState !== 'loading') place();

  function place() {
    if (!document.body) return;
    document.body.appendChild(bar);
    if (!SEL) { bar.textContent = '탐지 시점의 페이지입니다.'; return; }
    var el = null;
    try { el = document.querySelector(SEL.split('>>>').pop().trim()); } catch (e) {}
    if (!el) {
      bar.textContent = '탐지 시점의 페이지입니다. (이 항목은 iframe 내부라 위치 표시를 건너뜁니다)';
      return;
    }
    // 숨겨져 있던 요소이므로 보이게 되돌린 뒤 표시한다.
    var cur = el;
    while (cur && cur.nodeType === 1) {
      var cs = getComputedStyle(cur);
      if (cs.display === 'none') cur.style.setProperty('display', 'block', 'important');
      cur.style.setProperty('visibility', 'visible', 'important');
      cur.style.setProperty('opacity', '1', 'important');
      if (cs.position === 'absolute' || cs.position === 'fixed') cur.style.setProperty('position', 'static', 'important');
      cur.style.setProperty('left', 'auto', 'important');
      cur.style.setProperty('text-indent', '0', 'important');
      cur.style.setProperty('transform', 'none', 'important');
      cur.style.setProperty('clip', 'auto', 'important');
      cur.style.setProperty('clip-path', 'none', 'important');
      cur.style.setProperty('overflow', 'visible', 'important');
      if (parseFloat(cs.fontSize) <= 1) cur.style.setProperty('font-size', '15px', 'important');
      if (parseFloat(cs.height) <= 1) cur.style.setProperty('height', 'auto', 'important');
      cur = cur.parentElement;
    }
    el.classList.add('__ad_detector_hit');
    bar.textContent = '표시된 부분이 검출 위치입니다. 원래 화면에서는 보이지 않습니다.';
    setTimeout(function () { el.scrollIntoView({ block: 'center' }); }, 60);
  }
})();
</script>
"""


def build(html, origin_url, selector=None):
    """스냅샷 HTML 에 기준 주소와 표시 스크립트를 끼워 넣는다. (HTML, 함께 보낼 CSP 헤더 값) 을 돌려준다.

    저장한 HTML 에는 원래 누리집의 스크립트가 그대로 들어 있다. 해킹된 누리집이면 방문자를 광고 사이트로
    넘기는 스크립트도 있는데, 그대로 두면 훤히 화면 안에서 다시 실행된다. 그때의 화면을 보여 주는 데는
    스크립트가 필요 없으므로 우리 표시 스크립트(nonce)만 실행되게 한다.
    """
    nonce = secrets.token_urlsafe(16)
    injected = BASE_TAG.format(url=origin_url) + HIGHLIGHT.replace(
        "__SELECTOR__", json.dumps(selector or "")).replace("__NONCE__", nonce)
    # <head> 바로 뒤에 넣어야 상대 경로 자원이 원본 기준으로 풀린다.
    m = re.search(r"<head[^>]*>", html, re.I)
    page = html[:m.end()] + injected + html[m.end():] if m else injected + html
    csp = f"script-src 'nonce-{nonce}'; object-src 'none'; form-action 'none'"
    return page, csp
