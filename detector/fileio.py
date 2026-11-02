"""결과·조치 상태 파일을 안전하게 쓴다.

제자리에 바로 덮어쓰면 쓰는 도중 프로그램이 꺼질 때 반쯤 잘린 파일이 남는다. 조치 상태 파일이
깨지면 다음에 켤 때 빈 기록으로 시작해 담당자가 쌓은 조치·오탐 기록이 모두 사라진다.
그래서 옆에 임시 파일로 다 쓴 뒤 한 번에 바꿔 넣는다 (바꿔 넣기는 끝났거나 안 일어났거나 둘 중 하나다).
"""
import json
import os
import time

REPLACE_TRIES = 5        # 백신·탐색기가 잠깐 파일을 잡고 있으면 Windows 에서 바꿔 넣기가 실패한다


def write_json(path, doc, **dump_kw):
    folder = os.path.dirname(path) or "."
    os.makedirs(folder, exist_ok=True)
    tmp = f"{path}.{os.getpid()}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fp:
            json.dump(doc, fp, ensure_ascii=False, **dump_kw)
            fp.flush()
            os.fsync(fp.fileno())
        for i in range(REPLACE_TRIES):
            try:
                os.replace(tmp, path)
                return
            except PermissionError:
                if i == REPLACE_TRIES - 1:
                    raise
                time.sleep(0.1 * (i + 1))
    finally:
        if os.path.exists(tmp):
            try:
                os.remove(tmp)
            except OSError:
                pass
