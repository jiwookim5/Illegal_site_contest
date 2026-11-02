"""그림 속 글자 인식 시험용 자료(testsite16/files)를 만든다.

- 그림: Edge 로 광고 배너·포스터·정상 사진 흉내를 찍는다
- 스캔 PDF: 글자층 없이 그림만 든 PDF 를 직접 짠다 (JPEG 그대로 / 압축만 푼 RGB 픽셀 / 팩스식 흑백 압축 CCITT G4)

한 번 만들어 저장소에 넣어 두므로 평소에는 다시 돌릴 필요가 없다. Edge 와 pillow 가 필요하다.
    .venv\\Scripts\\python tools\\make_ocr_fixtures.py
"""
import io
import os
import zlib

from playwright.sync_api import sync_playwright

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "testsite16", "files")

BANNER = ("<div style='padding:28px 36px;background:#14213d;color:#fca311;font:bold 34px Malgun Gothic'>"
          "출장안마 24시 후불 예약<br><span style='font-size:26px;color:#fff'>카톡 op999 바로 상담</span></div>")
POSTER = ("<div style='padding:36px;background:#2b0a3d;color:#ffd166;font:bold 38px Malgun Gothic'>"
          "바카라 에볼루션 첫충 30%<br><span style='font-size:28px;color:#fff'>가입쿠폰 텔레그램 @bac777</span></div>")
PHOTO = ("<div style='padding:36px;background:#e9f5db;color:#283618;font:30px Malgun Gothic'>"
         "2026년 구민 체육대회<br>단체 사진 (구민체육센터)</div>")
SCAN_JPEG = ("<div style='padding:40px;background:#fff;color:#111;font:24px Batang,serif;width:620px'>"
             "<b style='font-size:30px'>공문 사본</b><br><br>주민 참여 예산 설명회를 다음과 같이 엽니다.<br>"
             "온라인카지노 무료머니 지급 문의 텔레그램 @scan777<br>기획예산과</div>")
SCAN_FAX = ("<div style='padding:40px;background:#fff;color:#000;font:26px Batang,serif;width:620px'>"
            "<b style='font-size:30px'>팩스 수신 문서</b><br><br>홀덤 입플 이벤트 진행중 텔레그램 @fax777<br>"
            "민원봉사과</div>")
SCAN_RAW = ("<div style='padding:40px;background:#fff;color:#111;font:24px Batang,serif;width:620px'>"
            "<b style='font-size:30px'>참석자 명단</b><br><br>"
            "급전대출 무직자 당일 승인 카톡 loan777<br>총무과</div>")


def shot(page, html, path, kind):
    page.set_content(f"<html><body style='margin:0;display:inline-block'>{html}</body></html>")
    page.locator("body > div").screenshot(path=path, type=kind, **({"quality": 90} if kind == "jpeg" else {}))


def pdf_with_image(image_stream, w, h, filt, extra=b"/ColorSpace /DeviceRGB /BitsPerComponent 8"):
    """글자층 없이 그림 하나만 페이지 가득 그린 PDF."""
    objs = [b"<< /Type /Catalog /Pages 2 0 R >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 %d %d] /Resources << /XObject << /Im1 4 0 R >> >> "
            b"/Contents 5 0 R >>" % (w, h),
            b"<< /Type /XObject /Subtype /Image /Width %d /Height %d %s "
            b"/Filter /%s /Length %d >>\nstream\n" % (w, h, extra, filt, len(image_stream)) + image_stream + b"\nendstream"]
    content = b"q %d 0 0 %d 0 0 cm /Im1 Do Q" % (w, h)
    objs.append(b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream")
    out, offs = b"%PDF-1.4\n", []
    for i, o in enumerate(objs, 1):
        offs.append(len(out))
        out += b"%d 0 obj\n" % i + o + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objs) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offs)
    out += b"trailer << /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (len(objs) + 1, xref)
    return out


def main():
    from PIL import Image

    os.makedirs(OUT, exist_ok=True)
    tmp = os.path.join(OUT, "_scan.jpg")
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="msedge")
        page = browser.new_page()
        shot(page, BANNER, os.path.join(OUT, "banner_ad.png"), "png")
        shot(page, POSTER, os.path.join(OUT, "poster.png"), "png")
        shot(page, PHOTO, os.path.join(OUT, "photo.jpg"), "jpeg")
        shot(page, SCAN_JPEG, tmp, "jpeg")
        shot(page, SCAN_RAW, os.path.join(OUT, "_raw.png"), "png")
        shot(page, SCAN_FAX, os.path.join(OUT, "_fax.png"), "png")
        browser.close()

    jpg = open(tmp, "rb").read()
    w, h = Image.open(io.BytesIO(jpg)).size
    open(os.path.join(OUT, "scan.pdf"), "wb").write(pdf_with_image(jpg, w, h, b"DCTDecode"))
    raw = Image.open(os.path.join(OUT, "_raw.png")).convert("RGB")
    open(os.path.join(OUT, "scan_flate.pdf"), "wb").write(
        pdf_with_image(zlib.compress(raw.tobytes()), raw.width, raw.height, b"FlateDecode"))
    # 팩스식 흑백 압축(CCITT G4). 공문 스캔에 흔하다. TIFF 로 압축한 뒤 압축 데이터만 꺼내 PDF 에 넣는다
    fax = Image.open(os.path.join(OUT, "_fax.png")).convert("L").point(lambda v: 255 if v > 128 else 0).convert("1")
    buf = io.BytesIO()
    fax.save(buf, "TIFF", compression="group4", tiffinfo={278: fax.height})     # 한 덩어리(strip)로
    tif = Image.open(io.BytesIO(buf.getvalue()))
    off, cnt = tif.tag_v2[273][0], tif.tag_v2[279][0]
    # TIFF 사진 해석(262)이 1(BlackIsZero)이면 PDF 쪽은 BlackIs1 true 라야 검은 글씨가 검게 그려진다
    black_is_1 = b"true" if tif.tag_v2.get(262, 1) == 1 else b"false"
    parms = (b"/ColorSpace /DeviceGray /BitsPerComponent 1 /DecodeParms << /K -1 /Columns %d /Rows %d "
             b"/BlackIs1 %s >>" % (fax.width, fax.height, black_is_1))
    open(os.path.join(OUT, "scan_ccitt.pdf"), "wb").write(
        pdf_with_image(buf.getvalue()[off:off + cnt], fax.width, fax.height, b"CCITTFaxDecode", parms))
    os.remove(os.path.join(OUT, "_fax.png"))
    os.remove(tmp)
    os.remove(os.path.join(OUT, "_raw.png"))
    print("OK", sorted(os.listdir(OUT)))


if __name__ == "__main__":
    main()
