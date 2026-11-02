"""출처가 있는 짧은 발췌와 별도 합성 자료를 오프라인 비교한다. URL에 접속하지 않는다."""
import argparse
from collections import Counter
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--engine-dir', type=Path, help='비교할 lexicon/precision_policy 사본 폴더')
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT / 'detector'))
    if args.engine_dir:
        sys.path.insert(0, str(args.engine_dir.resolve()))
    from findings import classify
    corpus = json.loads((ROOT / 'tools/data/context_corpus.json').read_text(encoding='utf-8'))
    rows = []
    for case in corpus['cases']:
        for strict in (False, True):
            verdict = classify(case['text'], strict=strict)
            detail = verdict['score']
            actual = 'ad' if verdict['is_ad'] else 'review' if verdict['review_candidate'] else 'normal'
            rows.append(dict(id=case['id'], kind=case['kind'], strict=strict,
                             expected=case['expected'], actual=actual,
                             matched=actual == case['expected'], detail=detail))
    report = dict(cases=len(corpus['cases']), checks=len(rows),
                  mismatches=sum(not r['matched'] for r in rows),
                  confusion=dict(Counter(f"{r['expected']}->{r['actual']}" for r in rows)),
                  rows=rows)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    for row in rows:
        if not row['matched']:
            print(row['id'], 'visible' if row['strict'] else 'hidden', row['expected'], '->', row['actual'])
    print(json.dumps({k: v for k, v in report.items() if k != 'rows'}, ensure_ascii=False))
    return int(bool(report['mismatches']))


if __name__ == '__main__':
    raise SystemExit(main())
