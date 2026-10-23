"""Build data/zh_words.json and data/zh_ngrams.json from the McBopomofo files
(run download_chinese.py first). Same compact JSON style as words.json / bigrams.json.

zh_words.json: single characters (字), grouped by pronunciation:
  {"ㄦˇ": {"爾": 4912, "耳": 1533, ...}, ...}

zh_ngrams.json: words of 2 or more characters (詞), grouped by first syllable,
then by the rest of the syllable sequence (the same shape as bigrams.json):
  {"ㄨㄛˇ": {"ㄇㄣ˙": {"我們": 73422}, ...}, ...}
  The rest of a longer word is space-separated: "ㄧ" -> "ㄕˊ ㄦˋ ㄋㄧㄠˇ" -> 一石二鳥

Syllables keep their tone marks (first tone has no mark). Keys are in Zhuyin
order (ㄅㄆㄇㄈ..., tones 1-2-3-4-5); words are most frequent first.

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
"""
import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
IN_DIR = os.path.join(DATA_DIR, "raw", "mcbopomofo")
WORDS_FILE = os.path.join(DATA_DIR, "curated", "zh_words.json")
NGRAMS_FILE = os.path.join(DATA_DIR, "curated", "zh_ngrams.json")

# Sort order for syllables: Zhuyin letters in alphabet order, then tone.
TONES = {"": 1, "ˊ": 2, "ˇ": 3, "ˋ": 4, "˙": 5}

MIN_COUNT = 0  # the word list is hand-checked, so a count of 0 just means "not seen in the corpus"

CHARSETS = {"big5", "big5e"}  # keep words whose characters are all in these sets

SECOND_READING = 10  # divisor for heterophony2 readings
OTHER_READING = 100  # divisor for the remaining readings of a char with a marked usual reading


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


def zhuyin_key(zhuyin):
    """Sort key: letters first, then tone, syllable by syllable."""
    key = []
    for syl in zhuyin.split(" "):
        tone = syl[-1] if syl[-1] in TONES else ""
        key.append((syl[: len(syl) - len(tone)], TONES[tone]))
    return key


def sort_keys(d):
    return {k: d[k] for k in sorted(d, key=zhuyin_key)}


def by_count(d):
    return dict(sorted(d.items(), key=lambda x: (-x[1], x[0])))


def build_words(rows):
    """{zhuyin: {char: count}} for single characters."""
    out = {}
    for word, count, zhuyin in rows:
        if len(word) == 1:
            out.setdefault(zhuyin, {})[word] = count
    return {k: by_count(v) for k, v in sort_keys(out).items()}


def build_ngrams(rows):
    """{first syllable: {rest of the syllables: {word: count}}} for longer words."""
    out = {}
    for word, count, zhuyin in rows:
        if len(word) > 1:
            first, rest = zhuyin.split(" ", 1)
            out.setdefault(first, {}).setdefault(rest, {})[word] = count
    return {k: {r: by_count(w) for r, w in sort_keys(v).items()} for k, v in sort_keys(out).items()}


if __name__ == "__main__":
    rows, missing = build()
    words, ngrams = build_words(rows), build_ngrams(rows)
    for path, data in ((WORDS_FILE, words), (NGRAMS_FILE, ngrams)):
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            json.dump(data, f, ensure_ascii=False)
    n_words = sum(len(v) for v in words.values())
    n_ngrams = sum(len(w) for v in ngrams.values() for w in v.values())
    print(f"{n_words} character readings under {len(words)} pronunciations -> {os.path.abspath(WORDS_FILE)}")
    print(f"{n_ngrams} word readings under {len(ngrams)} first syllables -> {os.path.abspath(NGRAMS_FILE)}")
    if missing:
        print(f"({missing} counted words had no reading and were skipped)")
