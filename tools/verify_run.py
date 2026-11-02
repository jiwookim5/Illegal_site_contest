"""python tools/verify_run.py <out/runs/실행ID> — 저장 파일의 변경·누락 검사."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "detector"))
from run_archive import verify


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("사용법: python tools/verify_run.py <실행 기록 폴더>")
    try:
        errors = verify(sys.argv[1])
    except (OSError, ValueError, KeyError) as exc:
        raise SystemExit(f"검사 실패: {exc}")
    for error in errors:
        print(error)
    print("체크섬 일치" if not errors else "변경 또는 누락 발견")
    raise SystemExit(1 if errors else 0)
