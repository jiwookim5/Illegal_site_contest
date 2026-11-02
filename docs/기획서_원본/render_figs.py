"""구조도·흐름도 HTML 을 이미지로 찍고, 화면 캡처의 상태 표시줄(맨 아래 줄)을 잘라낸다."""
import pathlib, sys
from playwright.sync_api import sync_playwright
from PIL import Image

html, out = sys.argv[1], pathlib.Path(sys.argv[2])
with sync_playwright() as p:
    b = p.chromium.launch(channel="msedge")
    pg = b.new_page(viewport={"width": 1100, "height": 900}, device_scale_factor=2)
    pg.goto(pathlib.Path(html).as_uri())
    pg.locator("#fig1").screenshot(path=str(out / "그림1_시스템구조.png"))
    pg.locator("#fig2").screenshot(path=str(out / "그림2_사용자흐름.png"))
    b.close()

# 상태 표시줄에는 결과 폴더 경로(사용자 폴더명)가 찍혀 있어 뺀다. 1.5배 캡처 기준 약 42px.
for name in ("화면1_탐지결과.png", "화면2_증거보기.png", "화면3_검색결과반사.png"):
    f = out / name
    im = Image.open(f)
    if im.height == 1140:
        im.crop((0, 0, im.width, im.height - 42)).save(f)
    print(name, Image.open(f).size)
