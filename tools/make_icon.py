"""프로그램 아이콘(훤히.ico)을 원본 그림 assets/icon_source.png 에서 만든다.

파란 바탕의 둥근 사각형에 돋보기, 렌즈 안에 가로줄 — 숨은 것을 찾아 지운다는 뜻이다.
원본은 생성 그림이라 가장자리에 점 같은 찌꺼기가 있다. 바탕 사각형만 잘라 내고
둥근 사각형 틀 밖은 투명하게 지운 뒤, 크기마다 따로 줄여(LANCZOS) ICO 하나에 담는다.
"""
import os

from PIL import Image, ImageDraw

SIZES = [16, 24, 32, 48, 64, 128, 256]
RADIUS = 0.17           # 둥근 모서리 반지름 (한 변 대비). 원본 그림의 모서리에 맞춘다


def clean(src):
    img = src.convert("RGBA")
    # 바탕 파랑(진한 테두리 포함)이 또렷한 점만 모아 사각형 범위를 잡는다. 흩어진 찌꺼기는 줄 단위 개수로 걸러 낸다
    w, h = img.size
    px = img.load()
    def solid(x, y):
        r, g, b, a = px[x, y]
        return a > 200 and b > 150 and b > r + 60
    rows = [y for y in range(h) if sum(solid(x, y) for x in range(0, w, 4)) > w // 16]
    cols = [x for x in range(w) if sum(solid(x, y) for y in range(0, h, 4)) > h // 16]
    box = (cols[0], rows[0], cols[-1] + 1, rows[-1] + 1)
    img = img.crop(box)
    side = max(img.size)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - img.width) // 2, (side - img.height) // 2))
    mask = Image.new("L", (side * 4, side * 4), 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, side * 4 - 1, side * 4 - 1), radius=int(side * 4 * RADIUS), fill=255)
    mask = mask.resize((side, side), Image.LANCZOS)
    alpha = Image.composite(square.getchannel("A"), Image.new("L", square.size, 0), mask)
    square.putalpha(alpha)
    return square


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "assets")
    base = clean(Image.open(os.path.join(out_dir, "icon_source.png")))
    images = [base.resize((s, s), Image.LANCZOS) for s in SIZES]
    ico = os.path.join(out_dir, "훤히.ico")
    images[-1].save(ico, format="ICO", sizes=[(s, s) for s in SIZES], append_images=images[:-1])
    images[-1].save(os.path.join(out_dir, "icon_preview.png"))
    print("생성:", ico, "/", ", ".join(f"{s}px" for s in SIZES))


if __name__ == "__main__":
    main()
