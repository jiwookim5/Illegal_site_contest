"""기획서 그림 3~5: 지금 화면을 1.5배로 찍어 구간을 잘라 붙인다. 사용: figs.py <작업 폴더> <출력 폴더>"""
import base64, pathlib, sys
from playwright.sync_api import sync_playwright
W, H = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])
DPR = 1.5

def clip(pg, name, y0, y1, x0=0, x1=1280):
    pg.screenshot(path=str(W / f"{name}.png"), clip={"x": x0, "y": y0, "width": x1 - x0, "height": y1 - y0})
    return W / f"{name}.png"

def compose(b, parts, out):
    """잘라 낸 구간을 위아래로 붙이고, 사이에 '중략' 표시(점선)를 넣는다."""
    imgs = "".join((f'<div class="cut"></div>' if i else "") + f'<img src="data:image/png;base64,{base64.b64encode(p.read_bytes()).decode()}">' for i, p in enumerate(parts))
    pg = b.new_page(viewport={"width": 2000, "height": 2000}, device_scale_factor=1)
    pg.set_content(f"""<style>body{{margin:0;background:#fff}} #c{{display:inline-block}} img{{display:block}}
      .cut{{height:24px;background:repeating-linear-gradient(90deg,#fff 0 10px,#fff 10px 20px);border-top:3px dashed #9a9a9a;margin-top:12px}}</style>
      <div id="c">{imgs}</div>""")
    pg.wait_for_timeout(500)
    pg.locator("#c").screenshot(path=str(out))
    pg.close()

with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    pg = b.new_page(viewport={"width": 1280, "height": 2000}, device_scale_factor=DPR)
    pg.goto("http://127.0.0.1:8911/"); pg.wait_for_timeout(2000)
    pg.add_style_tag(content="#st-right{visibility:hidden}")
    pg.get_by_role("button", name="결과 보기").first.click(); pg.wait_for_timeout(1500)
    # 그림 3: 요약·조치 확인 결과 + 목록 앞부분
    a = clip(pg, "f3a", 140, 422); bb = clip(pg, "f3b", 858, 1213)
    compose(b, [a, bb], H / "화면1_탐지결과.png")
    # 그림 4: 상세(조치·기록) — 판정 등급·조치 확인 + 증거 사진
    pg.evaluate("document.querySelector('a[href=\"#ad-4\"]').click()"); pg.wait_for_timeout(1500)
    a = clip(pg, "f4a", 140, 598); bb = clip(pg, "f4b", 1150, 1296)
    compose(b, [a, bb], H / "화면2_증거보기.png")
    # 그림 5: 검색엔진 추가 탐색 (검색은 하지 않음, 대상 도메인은 예시 주소)
    pg.evaluate("[...document.querySelectorAll('a,button')].find(e=>e.offsetParent&&e.innerText.includes('목록으로')).click()"); pg.wait_for_timeout(1000)
    pg.get_by_role("button", name="추가 탐색하기").first.click(); pg.wait_for_timeout(1500)
    pg.evaluate("""(()=>{const i=[...document.querySelectorAll('#stage-search input[type=text], input')].find(e=>e.value==='127.0.0.1:8768');
                    i.value='www.example.go.kr'; i.dispatchEvent(new Event('input',{bubbles:true})); i.dispatchEvent(new Event('change',{bubbles:true}));})()""")
    pg.wait_for_timeout(800)
    clip(pg, "f5", 228, 1008, 234, 1046)
    (H / "화면3_검색결과반사.png").write_bytes((W / "f5.png").read_bytes())
    b.close()
print("ok")
