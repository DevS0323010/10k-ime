"""Build data/curated/zh_keyed.json, the only Chinese file the web app loads,
from the McBopomofo files (run download_chinese.py first).

Every word in McBopomofo's dictionary is
kept, even with a count of 0: about half of the 4-character idioms (成語) were not
seen in the corpus, but they are still real words people type. Give count-0
words a small score (e.g. add 1 to every count) when ranking predictions.

Only words made of Big5 characters (tagged big5 or big5e in BPMFBase.txt) are
kept. The other ~8,600 characters are rare or Simplified forms and together
appear only about 20 times in the corpus.

A word with several readings is listed under each reading:
  - single characters: if McBopomofo marks a usual reading (heterophony1.list),
    that reading keeps the full count, the second reading (heterophony2.list)
    gets 1/10 of it and any other reading 1/100. Characters with no marked
    reading give the full count to every reading.
  - longer words: every listed reading keeps the full count (these are mostly
    tone-change variants like 一個 ㄧ/ㄧˊ/ㄧˋ, which people may type either way).

zh_keyed.json:
  {"exact":   [["111e", {"八": 13625, "吧": 6496, ...}], ...],
   "phrases": {"一一": 11, "一下": 3570, ...}}
  - "exact": every character and word under the 10-key code of its full
    reading, as [code, {word: count}] pairs sorted by code (a plain list, so
    JS keeps the order: it would move number-like object keys to the front).
  - "phrases": every word of 2 or more characters, sorted, for predicting
    the next characters after what was already typed.
  When one word lands on the same code twice (readings that type the same,
  such as ㄛ and ㄜ), it keeps the higher count instead of adding them.

The 10-key code, per syllable: 2 digits for the initial (60 = no initial),
1-2 digits for the rest, then a tone letter: e = 1st, c = ˊ, a = ˇ, b = ˋ, d = ˙.
KEY_CONSONANTS / KEY_VOWELS / KEY_TONES must match maps.js.
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
IN_DIR = os.path.join(DATA_DIR, "raw", "mcbopomofo")
KEYED_FILE = os.path.join(DATA_DIR, "curated", "zh_keyed.json")

MIN_COUNT = 0  # the word list is hand-checked, so a count of 0 just means "not seen in the corpus"

CHARSETS = {"big5", "big5e"}  # keep words whose characters are all in these sets

SECOND_READING = 10  # divisor for heterophony2 readings
OTHER_READING = 100  # divisor for the remaining readings of a char with a marked usual reading

# 10-key codes (same as maps.js).
KEY_CONSONANTS = {
    "": "60",
    "ㄅ": "11", "ㄆ": "12", "ㄇ": "13", "ㄈ": "14",
    "ㄉ": "21", "ㄊ": "22", "ㄋ": "23", "ㄌ": "24",
    "ㄍ": "31", "ㄎ": "32", "ㄏ": "33",
    "ㄐ": "41", "ㄑ": "42", "ㄒ": "43",
    "ㄓ": "51", "ㄔ": "52", "ㄕ": "53", "ㄖ": "54",
    "ㄗ": "41", "ㄘ": "42", "ㄙ": "43",
}
KEY_VOWELS = {
    "": "9", "ㄦ": "9",
    "ㄚ": "1", "ㄛ": "5", "ㄜ": "5", "ㄝ": "5",
    "ㄞ": "11", "ㄟ": "51", "ㄠ": "12", "ㄡ": "52",
    "ㄢ": "13", "ㄣ": "53", "ㄤ": "14", "ㄥ": "54",
    "ㄧ": "61", "ㄧㄚ": "2", "ㄧㄛ": "62", "ㄧㄜ": "61", "ㄧㄝ": "6", "ㄧㄞ": "21",
    "ㄧㄠ": "22", "ㄧㄡ": "62", "ㄧㄢ": "23", "ㄧㄣ": "63", "ㄧㄤ": "24", "ㄧㄥ": "64",
    "ㄨ": "72", "ㄨㄚ": "3", "ㄨㄛ": "7", "ㄨㄞ": "31", "ㄨㄟ": "71",
    "ㄨㄢ": "33", "ㄨㄣ": "73", "ㄨㄤ": "34", "ㄨㄥ": "74",
    "ㄩ": "4", "ㄩㄝ": "8", "ㄩㄢ": "43", "ㄩㄣ": "83", "ㄩㄥ": "84",
}
KEY_TONES = {"": "e", "ˊ": "c", "ˇ": "a", "ˋ": "b", "˙": "d"}


def is_zhuyin_symbol(word):
    """True for entries that are bare Zhuyin letters or tone marks (ㄅ, ˇ ...), not words."""
    return all("㄀" <= ch <= "ㄯ" or ch in "ˊˇˋ˙" for ch in word)


def read_pairs(path):
    """Yield (first field, rest of line as a list) for each non-empty line."""
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) >= 2 and not line.startswith("#"):
                yield parts[0], parts[1:]


def load_readings():
    """Return {word: [zhuyin, ...]} in file order, without duplicates, and the set of allowed chars."""
    readings = {}
    allowed = set()
    for char, rest in read_pairs(os.path.join(IN_DIR, "BPMFBase.txt")):
        if len(rest) >= 4 and rest[3] in CHARSETS:
            allowed.add(char)
        readings.setdefault(char, [])
        if rest[0] not in readings[char]:
            readings[char].append(rest[0])
    for word, rest in read_pairs(os.path.join(IN_DIR, "BPMFMappings.txt")):
        zhuyin = " ".join(rest)
        if len(rest) != len(word):  # syllable count must match character count
            continue
        readings.setdefault(word, [])
        if zhuyin not in readings[word]:
            readings[word].append(zhuyin)
    return readings, allowed


def load_usual(name):
    return {char: rest[0] for char, rest in read_pairs(os.path.join(IN_DIR, name))}


def build():
    readings, allowed = load_readings()
    first = load_usual("heterophony1.list")
    second = load_usual("heterophony2.list")

    rows = []
    missing = 0
    for word, rest in read_pairs(os.path.join(IN_DIR, "phrase.occ")):
        count = int(rest[0])
        if count < MIN_COUNT or is_zhuyin_symbol(word):
            continue
        if not all(ch in allowed for ch in word):
            continue
        if word not in readings:
            missing += 1
            continue
        for zhuyin in readings[word]:
            c = count
            if len(word) == 1 and word in first and len(readings[word]) > 1:
                if zhuyin == first[word]:
                    pass
                elif zhuyin == second.get(word):
                    c = count // SECOND_READING
                else:
                    c = count // OTHER_READING
            if c >= MIN_COUNT:
                rows.append((word, c, zhuyin))
    return rows, missing


def by_count(d):
    return dict(sorted(d.items(), key=lambda x: (-x[1], x[0])))


_syllable_codes = {}


def syllable_code(syl):
    """10-key code of one syllable, e.g. "ㄅㄚ" -> "111e"."""
    code = _syllable_codes.get(syl)
    if code is None:
        consonant = syl[0] if syl[0] in KEY_CONSONANTS else ""
        tone = syl[-1] if syl[-1] in KEY_TONES else ""
        vowel = syl[len(consonant): len(syl) - len(tone)]
        if vowel not in KEY_VOWELS:
            raise ValueError(f"no 10-key code for {syl!r}")
        code = KEY_CONSONANTS[consonant] + KEY_VOWELS[vowel] + KEY_TONES[tone]
        _syllable_codes[syl] = code
    return code


def key_code(zhuyin):
    return "".join(syllable_code(s) for s in zhuyin.split(" "))


def build_keyed(rows):
    """{"exact": [[code, {word: count}], ...], "phrases": {word: count}} for the web app."""
    exact, phrases = {}, {}
    for word, count, zhuyin in rows:
        bucket = exact.setdefault(key_code(zhuyin), {})
        if bucket.get(word, -1) < count:
            bucket[word] = count
        if len(word) > 1 and phrases.get(word, -1) < count:
            phrases[word] = count
    return {
        "exact": [[k, by_count(exact[k])] for k in sorted(exact)],
        "phrases": {w: phrases[w] for w in sorted(phrases)},
    }


if __name__ == "__main__":
    rows, missing = build()
    keyed = build_keyed(rows)
    os.makedirs(os.path.dirname(KEYED_FILE), exist_ok=True)
    with open(KEYED_FILE, "w", encoding="utf-8", newline="\n") as f:
        json.dump(keyed, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(rows)} word readings under {len(keyed['exact'])} key codes, "
          f"{len(keyed['phrases'])} phrases -> {os.path.abspath(KEYED_FILE)}")
    if missing:
        print(f"({missing} counted words had no reading and were skipped)")
