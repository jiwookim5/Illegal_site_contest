"""외부 페이지의 텍스트·담당자 메모를 CSV 수식으로 실행하지 않게 내보낸다."""
import unicodedata


def csv_text(value):
    text = "" if value is None else str(value)
    probe = text.lstrip()
    while probe and (probe[0].isspace() or unicodedata.category(probe[0]).startswith("C")):
        probe = probe[1:]
    if probe.startswith(("=", "+", "-", "@")) or text.startswith(("\t", "\r", "\n")):
        return "'" + text
    return text
