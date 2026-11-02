"""그림 속 글자를 Windows 에 내장된 글자 인식(Windows.Media.Ocr)으로 읽는다.

광고 문구를 그림으로 만들어 올리면 글자 기반 필터를 피한다(배너·포스터·스캔한 문서).
외부 서비스나 GPU 없이 Windows 가 가진 한국어 인식기를 쓴다. 비용이 들지 않고 그림이 밖으로 나가지 않는다.

- 한국어 인식기가 없거나(영어판 Windows 등) Windows 가 아니면 available() 이 False 이고, 부른 쪽은 건너뛴다.
- WinRT 호출은 비동기라 따로 만든 스레드의 이벤트 루프에서 돌린다
  (Playwright 동기 API 가 쓰는 스레드의 루프와 섞이지 않게).
"""
import asyncio
import threading

LANG = "ko"
MIN_SIDE = 16            # 이보다 작은 그림(아이콘·구분선)은 읽지 않는다
_state = {"checked": False, "engine": None, "max_dim": 0, "reason": ""}
_lock = threading.Lock()


def _run(coro):
    """새 스레드에서 코루틴을 끝까지 돌리고 결과를 돌려준다."""
    box = {}

    def target():
        try:
            box["value"] = asyncio.run(coro)
        except Exception as exc:          # 그림 하나를 못 읽어도 점검은 이어 간다
            box["error"] = exc

    th = threading.Thread(target=target, daemon=True)
    th.start()
    th.join(30)
    if "error" in box:
        raise box["error"]
    return box.get("value")


def available():
    """한국어 글자 인식을 쓸 수 있는가. 처음 한 번만 확인한다."""
    with _lock:
        if not _state["checked"]:
            _state["checked"] = True
            try:
                from winrt.windows.globalization import Language
                from winrt.windows.media.ocr import OcrEngine
                engine = OcrEngine.try_create_from_language(Language(LANG))
                if engine is None:
                    _state["reason"] = "이 PC 에 한국어 글자 인식 언어가 없습니다"
                else:
                    _state["engine"] = engine
                    _state["max_dim"] = OcrEngine.max_image_dimension
            except Exception as exc:
                _state["reason"] = f"Windows 글자 인식을 쓸 수 없습니다 ({type(exc).__name__})"
        return _state["engine"] is not None


def unavailable_reason():
    available()
    return _state["reason"]


async def _recognize(data):
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(data)
    await writer.store_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    w, h = decoder.pixel_width, decoder.pixel_height
    if min(w, h) < MIN_SIDE or max(w, h) > _state["max_dim"]:
        return None
    bitmap = await decoder.get_software_bitmap_async()
    result = await _state["engine"].recognize_async(bitmap)
    return [line.text for line in result.lines]


def read_lines(data):
    """그림 파일(PNG·JPG·GIF·BMP 등) 바이트 -> 읽은 줄 목록. 읽을 수 없거나 너무 작은 그림이면 None."""
    if not data or not available():
        return None
    try:
        return _run(_recognize(bytes(data)))
    except Exception:
        return None


IMAGE_MAGIC = ((b"\x89PNG\r\n\x1a\n", "PNG"), (b"\xff\xd8\xff", "JPEG"), (b"GIF87a", "GIF"),
               (b"GIF89a", "GIF"), (b"BM", "BMP"))


def image_kind(data):
    for magic, kind in IMAGE_MAGIC:
        if data[:len(magic)] == magic:
            return kind
    return None
