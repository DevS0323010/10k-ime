import json
import os
import re
import unicodedata


def strip_accents(s):
    return "".join(
        c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn"
    )


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
START_TOKEN = "<s>"
BIGRAM_THRESHOLD = 0.001
STOCK_NAMES = {
    "tom",
    "mary",
    "sami",
    "ziri",
    "yanni",
    "rima",
    "layla",
    "skura",
    "mennad",
    "algeria",
    "berber",
    "fadil",
    "kabyle",
    "kabylie",
    "baya",
    "boston",
}
LETTER_WORDS = {"a", "i"}
APOSTROPHE_STARTS = {"tis", "twas", "cause", "em"}
NAME_CAP = 1000
TARGETS = {}

# 7-key layout (same as en_maps in maps.js): key number for each letter.
# Apostrophes and hyphens go on the function key "-".
KEY_GROUPS = ["abcd", "efgh", "ijksz", "lmn", "opqr", "t", "uvwxy"]
KEY_OF = {c: str(i + 1) for i, g in enumerate(KEY_GROUPS) for c in g}
KEY_OF["'"] = KEY_OF["-"] = "-"
# Shown with a period after them ("Mr."); the period is not typed.
TITLES = {"mr", "mrs", "ms", "dr", "st", "jr", "sr", "vs"}
TITLE_PERIOD = re.compile(r"\b(" + "|".join(TITLES) + r")\.", re.IGNORECASE)


def by_count(d):
    return dict(sorted(d.items(), key=lambda x: (-x[1], x[0])))


def shown_form(word):
    """How a word appears in the candidate bar: titles get their period ("Mr.")."""
    return word + "." if word.lower() in TITLES else word


def build_keyed(words, bigrams):
    """en_keyed.json, the only file the web app loads:
      {"exact": [[code, {word: count}], ...],
       "next":  {"<s>": {"I": 317913, ...}, "i": {"don't": 17200, ...}, ...}}
    - "exact": every word under its 7-key code, sorted by code, words most
      frequent first. A list, not an object, because JS would move number-like
      keys such as "1" or "13" to the front of an object.
    - "next": the words that follow each word (bigrams), keyed by the previous
      word in lower case ("<s>" = start of a sentence), most frequent first.
    """
    exact = {}
    for word, count in words.items():
        code = "".join(KEY_OF[c] for c in word.lower().lstrip("'"))
        exact.setdefault(code, {})[shown_form(word)] = count
    following = {}
    for prev, nexts in bigrams.items():
        key = prev if prev == START_TOKEN else prev.lower()
        bucket = following.setdefault(key, {})
        for word, count in nexts.items():
            bucket[shown_form(word)] = count
    return {
        "exact": [[code, by_count(exact[code])] for code in sorted(exact)],
        "next": {k: by_count(following[k]) for k in sorted(following)},
    }


if __name__ == "__main__":
    with open(
        os.path.join(DATA_DIR, "raw", "tatoeba", "eng_sentences.tsv"),
        "r",
        encoding="utf-8",
    ) as f:
        sents = []
        for line in f:
            stripped = (
                strip_accents(line.strip().split("\t")[2])
                .strip()
                .replace("’", "'")
                .replace("‘", "'")
                .replace("´", "'")
                .replace("`", "'")
            )
            # "Mr. Smith": drop the title's period so it doesn't split the sentence
            stripped = TITLE_PERIOD.sub(r"\1", stripped)
            spl = [i for i in re.split(r"[^A-Za-z'\- ]+", stripped) if i.strip() != ""]
            sents.extend(spl)
        unigrams = {}
        bigrams = {}
        for sent in sents:
            first = True
            prev = START_TOKEN
            for word in sent.split():
                lower = word.lower()
                if lower in TARGETS:
                    print(sent)
                if (lower[0] == "'" and lower[1:] not in APOSTROPHE_STARTS) or lower[
                    0
                ] == "-":
                    lower = lower[1:]
                    word = word[1:]
                if len(lower) <= 1 and lower not in LETTER_WORDS:
                    prev = START_TOKEN
                    continue
                if lower[-1] == "-":
                    lower = lower[:-1]
                    word = word[:-1]
                if len(lower) <= 1 and lower not in LETTER_WORDS:
                    prev = START_TOKEN
                    continue
                if lower == lower.upper():
                    prev = START_TOKEN
                    continue
                if lower in unigrams:
                    unigrams[lower][0] += 1
                else:
                    unigrams[lower] = [1, {}]
                if not first:
                    unigrams[lower][1][word] = unigrams[lower][1].get(word, 0) + 1
                if prev not in bigrams:
                    bigrams[prev] = {}
                bigrams[prev][lower] = bigrams[prev].get(lower, 0) + 1
                prev = lower
                first = False
        for i, value in unigrams.items():
            if i.split("'")[0] in STOCK_NAMES:
                unigrams[i][0] = min(value[0], NAME_CAP)
        filtered_words = {
            max(i[1][1].items(), key=lambda x: x[1])[0]: i[1][0]
            for i in sorted(unigrams.items(), key=lambda x: -x[1][0])
            if i[1][0] > 10 and sum(i[1][1].values()) > 10
        }
        filtered_cases = {i.lower(): i for i in filtered_words}
        filtered_cases[START_TOKEN] = START_TOKEN
        filtered_bigrams = {
            filtered_cases[i]: {
                filtered_cases[j1]: j2
                for j1, j2 in j.items()
                if j1 in filtered_cases
                and j1.split("'")[0] not in STOCK_NAMES
                and j2
                >= max(
                    2,
                    BIGRAM_THRESHOLD
                    * filtered_words.get(filtered_cases[i], len(sents)),
                )
            }
            for i, j in bigrams.items()
            if i in filtered_cases
        }
        final_bigrams = {
            k: v for k, v in filtered_bigrams.items() if sum(v.values()) >= 50
        }
        folder = os.path.join(DATA_DIR, "curated")
        os.makedirs(folder, exist_ok=True)
        keyed = build_keyed(filtered_words, final_bigrams)
        out_file = os.path.join(folder, "en_keyed.json")
        with open(out_file, "w", encoding="utf-8", newline="\n") as f:
            json.dump(keyed, f, separators=(",", ":"))
        n_next = sum(len(v) for v in keyed["next"].values())
        print(f"{len(filtered_words)} words under {len(keyed['exact'])} key codes, "
              f"{n_next} bigrams after {len(keyed['next'])} words -> {os.path.abspath(out_file)}")
