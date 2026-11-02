"""본문 그림 속 광고 문구 (선택 기능, 기본 꺼짐).

광고를 글자가 아니라 그림(배너·포스터)으로 올리면 글자 필터도, 숨김 판정도 피한다.
페이지의 그림을 받아 Windows 글자 인식(ocr.py)으로 읽고, 화면에 보이는 글과 같은 기준으로 판정한다.
그림을 받고 읽는 데 시간이 들어 점검 설정에서 켰을 때만 하고, 같은 그림은 한 번만 읽는다.
결과는 추가 유형(result_extra.json)으로만 간다.
"""
import time

import ocr
from judgement import judge
from selector_js import BUILD_SELECTOR

CODE = "IMAGE_TEXT_AD(그림 속 광고 문구)"
GUIDE = ("그림을 내리거나 바꾸고, 올린 사람(아이피)을 차단합니다. 게시판에서 그림 올리기를 허용하면 "
         "올린 그림도 관리자 확인을 거치도록 합니다.")
PER_PAGE = 30            # 한 페이지에서 볼 그림 수
MAX_IMAGES = 200         # 한 번의 점검에서 받아 읽을 그림 수
BUDGET_SEC = 180         # 그림 받기·읽기에 쓰는 시간 상한
MAX_BYTES = 5 * 1024 * 1024
FETCH_TIMEOUT_MS = 10000

IMAGES_JS = r"""
(limit) => {
  BUILD_SELECTOR
  const out = [], seen = new Set();
  for (const img of document.images) {
    const src = img.currentSrc || img.src;
    if (!/^https?:/i.test(src) || seen.has(src)) continue;
    seen.add(src);
    out.push({ src, selector: buildSelector(img) });
    if (out.length >= limit) break;
  }
  return out;
}
""".replace("BUILD_SELECTOR", BUILD_SELECTOR.strip(), 1)


class ImageTextScanner:
    def __init__(self, request, manners, classify, deadline=None):
        self.request = request      # Playwright APIRequestContext (쿠키·UA 공유)
        self.manners = manners
        self.classify = classify
        self.deadline = deadline    # 참을 돌려주면 점검 시간 상한에 닿은 것
        self.deferred = set()
        self.on_checkpoint = None
        self.cache = {}             # 그림 주소 -> 읽은 글 (못 읽었으면 None)
        self.read = 0
        self.spent = 0.0
        # 글자 인식을 쓸 수 없는 PC 면 아무것도 하지 않고, 그 까닭을 점검 범위에 남긴다
        self.unavailable = "" if ocr.available() else ocr.unavailable_reason()

    def _text(self, src):
        if src in self.cache:
            return self.cache[src]
        if self.read >= MAX_IMAGES or self.spent >= BUDGET_SEC or (self.deadline and self.deadline()):
            self.deferred.add(src)
            return None
        text = None
        if (self.read < MAX_IMAGES and self.spent < BUDGET_SEC
                and not (self.deadline and self.deadline()) and self.manners.allowed(src)):
            self.read += 1
            self.manners.wait()
            t0 = time.perf_counter()
            try:
                resp = self.request.get(src, timeout=FETCH_TIMEOUT_MS, max_redirects=5)
                if resp.ok and int(resp.headers.get("content-length") or 0) <= MAX_BYTES:
                    data = resp.body()
                    if len(data) <= MAX_BYTES:
                        lines = ocr.read_lines(data)
                        text = " ".join(lines) if lines else None
            except Exception:
                text = None
            self.spent += time.perf_counter() - t0
        self.cache[src] = text
        if self.on_checkpoint: self.on_checkpoint()
        return text

    def check(self, frame, url, prefix=""):
        """프레임 안 그림들 가운데 광고 문구가 든 것."""
        if self.unavailable:
            return []
        try:
            images = frame.evaluate(IMAGES_JS, PER_PAGE)
        except Exception:
            return []
        rows = []
        for im in images:
            text = self._text(im["src"])
            if not text:
                continue
            # 그림 속 글은 사람에게 그대로 보이는 글이다. 보이는 글과 같은 엄격한 기준으로 본다
            verdict = self.classify(text, strict=True)
            if not (verdict["is_ad"] or verdict.get("review_candidate")):
                continue
            rows.append({
                "url": url, "location": prefix + im["selector"], "technique": "ETC",
                "evidence_text": text, "normalized": verdict["normalized"],
                "reason": f"그림 속 글자를 글자 인식(OCR)으로 읽은 광고 문구 (그림: {im['src'][:80]})",
                "keywords": verdict["evidence"], "extra_finding": CODE, "guide": GUIDE,
                "judgement": judge(verdict),
            })
        return rows
