"""난독화된 문자열을 사전 매칭이 가능한 형태로 되돌린다.

HOMOGLYPH / JAMO 탐지와 오탐 억제가 모두 이 모듈에 의존한다.
"""
import re
import unicodedata

CHO = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
JUNG = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
JONG = " ㄱㄲㄳㄴㄵㄶㄷㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅄㅅㅆㅇㅈㅊㅋㅌㅍㅎ"

ZERO_WIDTH = "​‌‍⁠﻿᠎"
# 화면에 그려지지 않거나 빈칸으로만 보이는 글자. 자모 사이에 끼워 음절 결합을 막는 데 쓰인다
# (보이지 않는 하이픈, 방향 표시 문자, 한글 채움 문자 'ㅤ'·반각 채움, 보이지 않는 연산자)
INVISIBLE = ZERO_WIDTH + "\u00ad\u200e\u200f\u3164\u115f\u1160\uffa0\u2061\u2062\u2063\u2064"
SEPARATORS = ".·・_\\-*^~|/\\s"

# 키릴·그리스 문자를 시각적으로 같은 라틴 문자로 되돌린다.
CONFUSABLES = {
    "а": "a", "е": "e", "о": "o", "р": "p", "с": "c", "у": "y", "х": "x",
    "і": "i", "ј": "j", "ѕ": "s", "һ": "h", "ԁ": "d", "ɡ": "g", "ν": "v",
    "А": "A", "В": "B", "Е": "E", "К": "K", "М": "M", "Н": "H", "О": "O",
    "Р": "P", "С": "C", "Т": "T", "Х": "X", "Ѕ": "S", "І": "I", "Ј": "J",
    "α": "a", "ο": "o", "ρ": "p", "τ": "t", "υ": "u", "Ι": "I", "Ο": "O",
    # 소문자 라틴과 형태가 겹치는 키릴 자모를 추가로 되돌린다
    "ь": "b", "Ь": "b", "в": "b", "м": "m", "т": "t", "к": "k", "н": "h",
    "Β": "B", "Κ": "K", "Μ": "M", "Ν": "N", "Ρ": "P", "Τ": "T", "Υ": "Y",
    "Ε": "E", "Ζ": "Z", "Η": "H", "Χ": "X", "γ": "y", "ι": "i", "κ": "k",
    # 실제 위장 광고에서 보이는 그 밖의 닮은꼴 (키릴 п·г·ӏ, 아르메니아 օ·ս·ո, 라틴 ɑ·ı·ɩ)
    "п": "n", "г": "r", "ӏ": "l", "ԛ": "q", "ԝ": "w", "ѵ": "v",
    "օ": "o", "ս": "u", "ո": "n", "ɑ": "a", "ı": "i", "ɩ": "i",
}

# NFKC 가 풀지 못하는 장식 글자. 실제 불법광고 연락처에 쓰인다 (텔 🅞🅝❹❾❽❾, 텔레 sʙᴍᴛ3)
EXTRA_FOLD = {}
for _i in range(26):
    _c = chr(ord("a") + _i)
    EXTRA_FOLD[chr(0x1F150 + _i)] = _c      # 🅐 검은 원 문자
    EXTRA_FOLD[chr(0x1F170 + _i)] = _c      # 🅰 검은 네모 문자
    EXTRA_FOLD[chr(0x1F1E6 + _i)] = _c      # 🇦 지역 표시 문자
for _i in range(10):
    EXTRA_FOLD[chr(0x2776 + _i)] = str((_i + 1) % 10)   # ❶~❿
    EXTRA_FOLD[chr(0x2780 + _i)] = str((_i + 1) % 10)   # ➀~➉
    EXTRA_FOLD[chr(0x278A + _i)] = str((_i + 1) % 10)   # ➊~➓
EXTRA_FOLD["⓿"] = "0"
for _i in range(26):
    EXTRA_FOLD[chr(0x249C + _i)] = chr(ord("a") + _i)   # ⒜ 괄호 문자 (NFKC 는 '(a)' 세 글자로 푼다)
for _s, _c in zip("ᴀʙᴄᴅᴇғɢʜɪᴊᴋʟᴍɴᴏᴘǫʀꜱᴛᴜᴠᴡʏᴢ", "abcdefghijklmnopqrstuvwyz"):
    EXTRA_FOLD[_s] = _c                     # 작은 대문자

# 글자 사이에 끼워 넣는 이모지·기호(☑️ ⚡ ⥄ ≈ 등). 사전 매칭 전에 걷어낸다.
_SYMBOL_CATS = ("So", "Sk", "Sm", "Me")
_VARIATION = re.compile("[\ufe00-\ufe0f\U000e0000-\U000e007f]")


def _strip_symbols(t: str) -> str:
    t = _VARIATION.sub("", t)
    return "".join(ch for ch in t if unicodedata.category(ch) not in _SYMBOL_CATS
                   or unicodedata.normalize("NFKC", ch).isalnum())


_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_GREEK = re.compile(r"[Ͱ-Ͽ]")
_FULLWIDTH = re.compile(r"[！-｠￠-￦]")
# 호환 자모(U+3131~)와 조합용 자모(U+1100~) 양쪽을 모두 본다.
_COMPAT_JAMO = re.compile("[\\u3131-\\u318E\\u1100-\\u11FF]")
_LATIN = re.compile(r"[A-Za-z]")
# 자음 자모 옆에 'ㅣ' 대신 끼운 라틴 l·I (카ㅈl노 → 카지노). 생김새로 속이는 닮은꼴 위장이다
_JAMO_LATIN_I = re.compile(r"([ㄱ-ㅎ])[lI]")
_HANGUL = re.compile(r"[가-힣]")
# 라틴 글자에 따로 붙인 결합 부호 (cạsịno: a + U+0323). 글자를 바꾸지 않고 모양만 흐린다
_COMBINING_AFTER_LATIN = re.compile(r"(?<=[A-Za-z])[\u0300-\u036f\u1ab0-\u1aff\u1dc0-\u1dff\u20d0-\u20ff\ufe20-\ufe2f]+")
# 자모 사이에 끼운 문장부호 (ㅋ,ㅏ,ㅈ / ㅂ。ㅏ。ㅋ). 마침표·가운뎃점은 SEPARATORS 가 이미 지운다
_JAMO_PUNCT = re.compile(r"(?<=[\u3131-\u318e])[,，、。｡'\"`]+(?=[\u3131-\u318e])")
_HALFWIDTH_JAMO = re.compile(r"[\uffa1-\uffdc]")


def _clean_invisible(t: str) -> str:
    t = "".join(ch for ch in t if ch not in INVISIBLE)
    return _JAMO_PUNCT.sub("", t)


def compose_jamo(text: str) -> str:
    """분해된 호환 자모열을 음절로 재결합한다. (ㅋㅏㅈㅣㄴㅗ -> 카지노)"""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        ci = CHO.find(c)
        if ci >= 0 and i + 1 < n:
            vi = JUNG.find(text[i + 1])
            if vi >= 0:
                ti, step = 0, 2
                if i + 2 < n:
                    cand = JONG.find(text[i + 2])
                    # 다음 글자가 또 중성이면 그 자음은 다음 음절의 초성이다
                    nxt_is_jung = i + 3 < n and JUNG.find(text[i + 3]) >= 0
                    if cand > 0 and not nxt_is_jung:
                        ti, step = cand, 3
                out.append(chr(0xAC00 + (ci * 21 + vi) * 28 + ti))
                i += step
                continue
        out.append(c)
        i += 1
    return "".join(out)


# 조합용 자모(U+1100 블록)를 호환 자모로 되돌리는 표.
# NFKC가 호환 자모를 초성 전용 코드로 바꿔버리면 종성을 붙일 수 없으므로,
# 재결합은 반드시 NFKC보다 먼저 수행한다.
_CONJOINING = {}
for _i, _c in enumerate(CHO):
    _CONJOINING[chr(0x1100 + _i)] = _c
for _i, _c in enumerate(JUNG):
    _CONJOINING[chr(0x1161 + _i)] = _c
_CONJOINING_BACK = dict(_CONJOINING)


def normalize(text: str) -> str:
    """사전 매칭 직전 단계까지 정규화한다."""
    t = _clean_invisible(text)
    t = _COMBINING_AFTER_LATIN.sub("", t)
    t = "".join(CONFUSABLES.get(ch, EXTRA_FOLD.get(ch, ch)) for ch in t)
    t = _strip_symbols(t)                         # ⓐ 같은 원문자는 NFKC 가 풀도록 남긴다
    t = re.sub(f"[{SEPARATORS}]+", "", t)         # 글자 사이 끼워넣은 구분자 제거
    t = "".join(_CONJOINING.get(ch, ch) for ch in t)
    t = _JAMO_LATIN_I.sub(r"\1ㅣ", t)
    t = compose_jamo(t)                           # NFKC보다 앞서야 한다
    t = unicodedata.normalize("NFKC", t)          # 전각/반각, 호환 문자 통일
    # NFKC가 전각 기호를 ASCII로 풀어놓으므로 구분자를 한 번 더 제거하고,
    # 결합되지 못한 자모는 호환 자모 표기로 되돌려 표기를 일관되게 유지한다.
    t = "".join(_CONJOINING_BACK.get(ch, ch) for ch in t)
    t = re.sub(f"[{SEPARATORS}]+", "", t)
    return t.lower()


def has_jamo_obfuscation(text: str) -> bool:
    """자모 분해 기법이 쓰였는가.

    'ㅋㅋㅋ', 'ㅇㅇ' 같은 통상적 표현과 구분하기 위해,
    재결합했을 때 실제로 한글 음절이 만들어지는 경우만 인정한다.
    """
    # 반각 한글 자모(ﾻￂﾸ)는 요즘 글에 쓰이지 않는다. 그 자체로 자모를 흐린 표기다
    if _HALFWIDTH_JAMO.search(text) and _HANGUL.search(normalize(text)):
        return True
    if not _COMPAT_JAMO.search(text):
        return False
    stripped = _clean_invisible(text)
    # 조합용 자모(U+1100 블록)도 호환 자모로 맞춘 뒤에 재결합을 시도해야 한다.
    mapped = "".join(_CONJOINING.get(ch, ch) for ch in stripped)
    before = len(_HANGUL.findall(stripped))
    after = len(_HANGUL.findall(compose_jamo(mapped)))
    return after > before


def _is_disguised_letter(ch: str) -> bool:
    """ASCII 글자 한 자로 되돌아가는 비ASCII 글자인가.

    전각 라틴뿐 아니라 수학용 볼드(U+1D400~), 원문자 등 NFKC가 ASCII로
    되돌리는 글자를 한 번에 포착한다. '㈜'나 '½' 같은 기호는
    글자 범주가 아니므로 걸리지 않고, '㎏'·'℡'·'№'·'™' 처럼 여러 글자로 풀리는
    단위·약물 기호도 위장 글자가 아니다.
    """
    if ch in EXTRA_FOLD:
        return True
    cat = unicodedata.category(ch)
    # ⓐ 같은 원문자는 기호(So) 범주지만 NFKC 로 라틴 글자가 된다
    if ch.isascii() or not (cat.startswith("L") or cat == "So"):
        return False
    folded = unicodedata.normalize("NFKC", ch)
    return len(folded) == 1 and folded.isascii() and folded.isalnum()


# 문서에 단위로 흔히 쓰이는 글자 (500mℓ, 10µg). 라틴 글자로 풀리지만 위장으로 보지 않는다
_UNIT_LETTERS = set("ℓµ")
_SEP_RE = re.compile(f"[{SEPARATORS}{ZERO_WIDTH}－．＿／｜]+")


_FULLWIDTH_DIGIT = re.compile(r"[０-９]")


def _latinish(ch: str) -> bool:
    return ((ch.isascii() and ch.isalnum()) or ch in CONFUSABLES or _is_disguised_letter(ch)
            or bool(_FULLWIDTH_DIGIT.match(ch)))


def disguised_chars(text: str):
    """라틴 글자처럼 읽히는 낱말 안에 섞여 든 위장 글자들.

    닮은꼴 위장은 'саsinо', 'ｃａｓｉｎｏ', '텔 🅞🅝❹❾❽❾' 처럼 위장 글자가 다른 라틴(꼴) 글자와
    이어져 하나의 낱말로 읽혀야 의미가 있다. 날짜의 '～', '（주）', 단위 'μg', 목록 번호 'ⓐ'처럼
    홀로 쓰인 전각·특수 기호는 공공 문서에 흔하므로 세지 않는다.
    """
    t = _SEP_RE.sub("", text)
    out, run = [], []
    for ch in t + "\0":
        if _latinish(ch) and ch not in _UNIT_LETTERS:
            run.append(ch)
            continue
        fake = [c for c in run if not c.isascii()]
        lettered = any((EXTRA_FOLD.get(c) or unicodedata.normalize("NFKC", c)).isalpha() for c in run)
        # 전각 숫자만 이어진 경우는 연락처처럼 길 때만 위장으로 본다 ('２０２６년' 같은 표기는 제외)
        if fake and not lettered and len(fake) < 7:
            fake = []
        if len(run) >= 2 and fake:
            plain = [c for c in run if c.isascii() and c.isalpha()]
            # 키릴·그리스 글자만으로 된 낱말은 그 언어 글일 수 있다. ASCII 글자와 섞였거나
            # 전각·수학용·원문자처럼 그 자체로 위장용인 글자일 때만 위장으로 본다
            if plain or all(c not in CONFUSABLES for c in fake) or _spells_keyword(run):
                out.extend(fake)
        run = []
    return out


def _spells_keyword(run) -> bool:
    """키릴·그리스 글자만으로 쓴 낱말이 라틴으로 읽으면 광고 낱말인가 (ТОТО → toto, СASINO).

    러시아어·그리스어 낱말은 그 언어 글일 수 있어 위장으로 보지 않지만, 읽은 꼴이 도박·성인 낱말이면 위장이다.
    """
    import lexicon                       # lexicon 이 이 모듈을 불러오므로 쓸 때 불러온다
    word = "".join(CONFUSABLES.get(c, c) for c in run).lower()
    return any(len(w) >= 3 and w.isascii() and w in word
               for c in ("STRONG", "TOPIC", "MEDIUM") for w in getattr(lexicon, c))


def jamo_latin_i(text: str) -> bool:
    """자음 자모 옆에 'ㅣ' 대신 라틴 l·I 를 끼웠는가 (카ㅈl노)."""
    return bool(_JAMO_LATIN_I.search(_SEP_RE.sub("", text)))


def has_homoglyph(text: str) -> bool:
    """닮은꼴 글자 위장이 쓰였는가."""
    return bool(disguised_chars(text)) or jamo_latin_i(text) or bool(_COMBINING_AFTER_LATIN.search(text))


def describe_homoglyph(text: str) -> str:
    """어떤 종류의 닮은꼴 글자가 몇 자 섞였는지 설명한다."""
    kinds = {}
    for ch in disguised_chars(text):
        if _FULLWIDTH.match(ch):
            kind = "전각 문자"
        elif _CYRILLIC.match(ch):
            kind = "키릴 문자"
        elif _GREEK.match(ch):
            kind = "그리스 문자"
        elif ch in EXTRA_FOLD:
            kind = "장식 문자"
        else:
            kind = "특수 라틴 변형"
        kinds[kind] = kinds.get(kind, 0) + 1
    if jamo_latin_i(text):
        kinds["'ㅣ' 대신 라틴 l"] = len(_JAMO_LATIN_I.findall(_SEP_RE.sub("", text)))
    if _COMBINING_AFTER_LATIN.search(text):
        kinds["결합 부호"] = len(_COMBINING_AFTER_LATIN.findall(text))
    if not kinds:
        return "닮은꼴 글자 혼용"
    return ", ".join(f"{k} {v}자" for k, v in kinds.items()) + " 혼용"


# 라틴 글자 자리에 끼워 넣는 숫자·기호 치환 (t0t0, c4sino, b3t ...).
# '1' 은 l 로도 i 로도 쓰인다 (be11y, cas1n0) 그래서 두 가지로 되돌려 본다.
_LEET = {"0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b", "@": "a", "$": "s"}
LEET = str.maketrans(_LEET)
LEET_I = str.maketrans(dict(_LEET, **{"1": "i"}))
# 라틴 글자가 섞인 낱말 안의 숫자만 바꾼다. 숫자만 이어진 전화번호(010-7070-...)가 'toto' 로
# 읽히지 않게 하기 위함이다.
_LEET_RUN = re.compile(r"[a-z0-9@$]+")
_HAS_LETTER = re.compile(r"[a-z]")


def _deleet_with(normalized: str, table) -> str:
    def token(match):
        value = match.group(0)
        if not _HAS_LETTER.search(value):
            return value
        # Normalization joins URL/email/telephone separators. Long numeric IDs
        # must not become words merely because a Latin host is now adjacent.
        parts = re.split(r"(\d{3,})", value)
        return "".join(part if part.isdigit() and len(part) >= 3 else part.translate(table)
                       for part in parts)
    return _LEET_RUN.sub(token, normalized)


def deleet_all(normalized: str):
    """숫자 치환을 되돌린 보조 표기들 ('1' 을 l 로 본 것과 i 로 본 것).

    사전 매칭에만 쓴다. 표시용 문자열로는 쓰지 않는다.
    """
    return {_deleet_with(normalized, LEET), _deleet_with(normalized, LEET_I)}


# 한글 사이에 끼운, 자모와 생김새가 닮은 숫자·라틴 글자 (카ㅈ1노, 안전놀0l터, 머7튀)
_DIGIT_JAMO = {"0": "ㅇ", "o": "ㅇ", "1": "ㅣ", "l": "ㅣ", "i": "ㅣ", "|": "ㅣ", "7": "ㄱ"}
_HANGULISH = "[가-힣\u3131-\u318e]"
_DIGIT_IN_HANGUL = re.compile(f"(?<={_HANGULISH})[01li|7o]+(?={_HANGULISH})")


def attach_finals(text: str) -> str:
    """받침 없는 음절 뒤에 떼어 둔 자음을 받침으로 붙인다 (머ㄱ튀 → 먹튀, 노ㄹ이터 → 놀이터).

    다음 글자가 음절일 때만 붙인다. '좋아ㅋㅋ' 처럼 글 끝에 붙인 자음은 그대로 둔다.
    """
    out = list(text)
    for i in range(1, len(out) - 1):
        s, c, nxt = out[i - 1], out[i], out[i + 1]
        ti = JONG.find(c)
        if ti > 0 and "가" <= s <= "힣" and (ord(s) - 0xAC00) % 28 == 0 and "가" <= nxt <= "힣":
            out[i - 1], out[i] = chr(ord(s) + ti), ""
    return "".join(out)


def hangul_alts(normalized: str):
    """한글 위장을 다르게 풀어 본 보조 표기들. [(기법, 표기)]

    HOMOGLYPH: 한글 사이 숫자·라틴 글자를 닮은 자모로 (카ㅈ1노 → 카지노, 머7튀 → 먹튀)
    JAMO     : 떼어 낸 받침을 앞 음절에 붙여 (머ㄱ튀 → 먹튀)
    사전 매칭에만 쓴다. 이 표기에서만 광고 낱말이 나올 때 그 기법으로 본다.
    """
    out = []
    digit = _DIGIT_IN_HANGUL.sub(lambda m: "".join(_DIGIT_JAMO[c] for c in m.group(0)), normalized)
    if digit != normalized:
        out.append(("HOMOGLYPH", attach_finals(compose_jamo(digit))))
    final = attach_finals(normalized)
    if final != normalized:
        out.append(("JAMO", final))
    return out


def describe_jamo(text: str) -> str:
    """분해된 자모가 몇 자이고 무엇으로 재결합되는지 설명한다."""
    count = len(_COMPAT_JAMO.findall(text)) + len(_HALFWIDTH_JAMO.findall(text))
    return f"분해된 자모 {count}자를 재결합 → '{normalize(text)}'"
