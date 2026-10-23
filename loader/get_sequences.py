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
                if (lower[0] == "'" and lower[1:] not in APOSTROPHE_STARTS) or lower[0] == "-":
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
        folder = os.path.join(DATA_DIR, "curated")
        os.makedirs(folder, exist_ok=True)
        with open(os.path.join(folder, "words.tsv"), "w", encoding="utf-8") as f:
            for k, v in filtered_words.items():
                print(k, v, sep="\t", file=f)
        with open(os.path.join(folder, "bigrams.tsv"), "w", encoding="utf-8") as f:
            for k, v in filtered_bigrams.items():
                if sum(v.values()) < 50:
                    continue
                print(
                    k,
                    "\t".join(
                        f"{v1}:{v2}"
                        for v1, v2 in sorted(v.items(), key=lambda x: -x[1])
                    ),
                    sep="\t",
                    file=f,
                )
