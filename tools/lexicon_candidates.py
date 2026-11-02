r"""점검 사전에 넣을 후보 단어의 오탐·미탐 시험.

사전 파일은 고치지 않는다. 후보를 한 개씩 메모리의 사전에 더해 보고 아래를 확인한 뒤,
통과한 단어와 걸린 이유를 JSON 으로 남긴다. 사전에 이미 있는 단어는 잠시 뺀 상태에서 시험하므로
넣은 뒤에 다시 돌려도 같은 결과가 나온다.

  1. 새로 광고가 되는 정상 문장(오탐)이 없다
       - 기존 말뭉치(lexicon_real 의 OK, 시험 사이트의 정상 게시글·오탐 함정 문구)
       - 후보에 대해 사람이 쓴 정상 문장(spec 의 benign)과 예방 교육·보도 문장(자동 생성)
  2. 광고에서 정상이 되는 문장(미탐)이 없다 (lexicon_real 의 AD, spec 의 ads)
  3. 통과한 단어를 모두 함께 더해도 1·2 가 유지된다

spec 파일(JSON):
  {"name": "strong", "category": "STRONG" | "TOPIC" | "MEDIUM" | "WEAK" | "CAUTION",
   "words": ["단어", ...],
   "benign": {"단어": ["정상 문장", ...]},      # 일상어로 쓰인 실제 같은 문장. 광고로 판정되면 탈락
   "ads": {"단어": ["광고 문장", ...]}}          # 있으면 광고로 판정돼야 한다

    .venv\Scripts\python tools\lexicon_candidates.py spec.json -o result.json
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "detector", ROOT / "tools", ROOT):
    sys.path.insert(0, str(p))
sys.stdout.reconfigure(encoding="utf-8")

import lexicon  # noqa: E402
from findings import classify  # noqa: E402
import lexicon_real  # noqa: E402
from testsite.scenarios.benign_pool import BENIGN_PUBLIC_POSTS, FALSE_POSITIVE_TRAPS  # noqa: E402

CATEGORIES = ("STRONG", "TOPIC", "MEDIUM", "WEAK", "CAUTION")

# 확정 표현(STRONG)은 그 말만 있어도 광고로 보는 것이 사전의 약속이라 '연구 논문' 문장은 시험하지 않는다
GENERIC = {
    "예방 교육": "{w} 예방 교육 안내",
    "보도": "{w} 관련 보도: 판매 일당 검거",
    "논문": "{w}에 관한 연구 논문 소개",
}


def _corpus():
    texts = list(lexicon_real.OK)
    for post in BENIGN_PUBLIC_POSTS + FALSE_POSITIVE_TRAPS:
        title, summary, content = post.get("title", ""), post.get("summary", ""), post.get("content", "")
        texts += [title, summary, content, f"{title}\n{summary}", f"{title}\n{summary}\n{content}"]
    ads = [t for t in lexicon_real.AD if t not in lexicon_real.ALLOWED_MISS]
    return list(dict.fromkeys(t for t in texts if t)), ads


def verdicts(texts):
    """문장 -> (일반 판정, 보이는 글 판정). 사전이 바뀔 때마다 VERSION 을 올려 판정 기억을 비운다."""
    lexicon.VERSION += 1
    return {t: (classify(t)["is_ad"], classify(t, strict=True)["is_ad"]) for t in texts}


def _lists():
    return {c: getattr(lexicon, c) for c in CATEGORIES}


def run(spec):
    cat, words = spec["category"], list(dict.fromkeys(spec["words"]))
    if cat not in CATEGORIES:
        raise SystemExit(f"알 수 없는 분류: {cat}")
    target = getattr(lexicon, cat)
    benign_extra, ads_extra = spec.get("benign", {}), spec.get("ads", {})
    texts, ads = _corpus()
    # 후보가 이미 사전에 있으면 잠시 뺀 상태를 기준으로 삼는다
    removed = {c: [w for w in words if w in lst] for c, lst in _lists().items()}
    for c, ws in removed.items():
        for w in ws:
            getattr(lexicon, c).remove(w)
    try:
        base_texts, base_ads = verdicts(texts), verdicts(ads)
        results = {}

        def check(added):
            """added 를 더한 사전으로 말뭉치를 다시 판정해 달라진 것을 모은다."""
            for w in added:
                target.append(w)
            try:
                now_texts, now_ads = verdicts(texts), verdicts(ads)
            finally:
                for w in added:
                    target.remove(w)
            fp = [t for t in texts if now_texts[t] != base_texts[t] and any(now_texts[t])]
            fn = [t for t in ads if now_ads[t] != base_ads[t] and not all(now_ads[t]) and all(base_ads[t])]
            return fp, fn

        for w in words:
            reasons = []
            fp, fn = check([w])
            reasons += [f"기존 정상 문구가 광고로 바뀜: {t[:60]}" for t in fp]
            reasons += [f"기존 광고가 정상으로 바뀜: {t[:60]}" for t in fn]
            target.append(w)
            try:
                lexicon.VERSION += 1
                mine = list(benign_extra.get(w, []))
                templates = [v for k, v in GENERIC.items() if not (cat == "STRONG" and k == "논문")]
                mine += [t.format(w=w) for t in templates]
                for text in mine:
                    got = (classify(text)["is_ad"], classify(text, strict=True)["is_ad"])
                    if any(got):
                        reasons.append(f"정상 문장이 광고로 판정됨: {text[:70]}")
                for text in ads_extra.get(w, []):
                    if not classify(text)["is_ad"]:
                        reasons.append(f"광고 문장이 잡히지 않음: {text[:70]}")
            finally:
                target.remove(w)
            results[w] = {"pass": not reasons, "reasons": reasons}

        passed = [w for w in words if results[w]["pass"]]
        fp, fn = check(passed)
        combined = {"pass": not (fp or fn),
                    "reasons": [f"합쳤을 때 정상→광고: {t[:60]}" for t in fp] + [f"합쳤을 때 광고→정상: {t[:60]}" for t in fn]}
    finally:
        for c, ws in removed.items():
            getattr(lexicon, c).extend(ws)
        lexicon.VERSION += 1
    return {"name": spec.get("name", cat), "category": cat, "words": results,
            "passed": passed, "rejected": [w for w in words if not results[w]["pass"]],
            "combined": combined, "corpus": {"정상": len(texts), "광고": len(ads)}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    parser.add_argument("-o", "--out", type=Path)
    args = parser.parse_args()
    result = run(json.loads(args.spec.read_text(encoding="utf-8-sig")))
    for w, r in result["words"].items():
        print(("통과 " if r["pass"] else "탈락 ") + w)
        for reason in r["reasons"]:
            print("    -", reason)
    print(f"[{result['name']}] 통과 {len(result['passed'])} · 탈락 {len(result['rejected'])} · "
          f"합쳐서 시험 {'통과' if result['combined']['pass'] else '실패'}  (말뭉치 {result['corpus']})")
    for reason in result["combined"]["reasons"]:
        print("    -", reason)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
