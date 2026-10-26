#!/usr/bin/env python3
"""Tune en_rank: how many completions (longer words) to show, and their divisor.
Standard library only. Python is for testing and tuning; JS is for the web app.

It loads the same data/curated/en_keyed.json as the web app, ranks candidates
with a Python copy of en_rank in read_data.js, and replays real sentences
word by word to count the keypresses each setting costs.

Typing one word (same cost model as optimize_layout.py):
  after j keys the word may be in the list at position p:
    p = 1          -> j + --cost-space (1)   press space
    p = 2..--bar   -> j + --cost-bar   (2)   tap the bar
    p > --bar      -> j + --cost-more  (4)   open the dropdown, then tap
  The cheapest j is used. Before any key (j = 0) the bar already shows the
  next-word guesses; picking one costs a tap (no space: space with nothing
  typed is a real space). Words not in the word list cost letters + 1.

Scoring modes (--score):
  ratio   your current en_rank: bigram counts are scaled by the smallest
          bigram/unigram ratio among the candidates, then max(unigram, bigram).
  interp  lam * P(w | prev) + (1 - lam) * P(w); unigrams only when prev has
          no bigram data. --lam is the bigram weight.

Usage:
  python tune_en_rank.py --sentences ../data/raw/tatoeba/eng_sentences.tsv
  python tune_en_rank.py --sentences ... --completions 0 1 2 3 4 5 6 --divisor 1.2 8
  python tune_en_rank.py --sentences ... --score ratio interp --every 10 --offset 3

Note: en_keyed.json was counted from all Tatoeba sentences, so testing on them
is a little optimistic. --every 10 --offset N tests on one tenth of them by id;
for a fair test, build en_keyed.json from the other nine tenths.
"""
import argparse
import json
import os
import re
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")

# Must match en_maps in maps.js and KEY_GROUPS in get_sequences.py.
KEY_GROUPS = ["abcd", "efgh", "ijksz", "lmn", "opqr", "t", "uvwxy"]
KEY_OF = {c: str(i + 1) for i, g in enumerate(KEY_GROUPS) for c in g}
KEY_OF["'"] = KEY_OF["-"] = "-"
TITLES = {"mr", "mrs", "ms", "dr", "st", "jr", "sr", "vs"}
START = "<s>"
TOP_UNI = 16  # longer words kept per prefix from word counts (more than any bar needs)


def en_code(word):
    """Same as en_code in read_data.js."""
    w = word.lower()
    if w.startswith("'"):
        w = w[1:]
    if w.endswith("."):
        w = w[:-1]
    return "".join(KEY_OF.get(c, "") for c in w)


class Ranker:
    def __init__(self, path):
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        self.uni, self.exact, self.top = {}, {}, {}
        for code, words in data["exact"]:
            self.exact[code] = list(words.items())  # most frequent first
            for w, c in words.items():
                self.uni[w] = c
        # best TOP_UNI longer words for each proper prefix of a code
        for w, c in sorted(self.uni.items(), key=lambda x: -x[1]):
            code = en_code(w)
            for j in range(1, len(code)):
                t = self.top.setdefault(code[:j], [])
                if len(t) < TOP_UNI:
                    t.append(w)
        self.uni_total = sum(self.uni.values())
        self.next = {k: list(v.items()) for k, v in data["next"].items()}
        self.next_total = {k: sum(c for _, c in v) for k, v in self.next.items()}
        self.lower = {w.lower().rstrip("."): w for w in self.uni}  # typed form -> list form
        self._codes = {}
        self._filtered = {}
        self._ranked = {}

    def code(self, w):
        c = self._codes.get(w)
        if c is None:
            c = self._codes[w] = en_code(w)
        return c

    def next_keys(self, prev, seq):
        """en_next_keys: bigram words after prev whose code starts with seq."""
        key = (prev, seq)
        r = self._filtered.get(key)
        if r is None:
            base = self.next.get(prev, []) if len(seq) <= 1 else self.next_keys(prev, seq[:-1])
            r = [(w, c) for w, c in base if self.code(w).startswith(seq)]
            self._filtered[key] = r
        return r

    def rank(self, prev, seq, n_longer, divisor, mode, lam):
        """Candidate list, slot 1 first. Mirrors en_rank: slot 1 = best exact
        word, then other exact words and the n_longer best longer words (score
        / divisor) sorted together."""
        if prev == "":
            prev = START
        memo_key = (prev, seq, n_longer, divisor, mode, lam)
        hit = self._ranked.get(memo_key)
        if hit is not None:
            return hit
        nxt = self.next.get(prev, []) if seq == "" else self.next_keys(prev, seq)
        # Every word with code prefix seq is either exact or in self.top[seq]
        # (best by count) or in nxt (bigram words), so these are all the words
        # that can reach the top n_longer, without scanning thousands of words.
        cand = {}
        if seq:
            for w, c in self.exact.get(seq, []):
                cand[w] = c
            for w in self.top.get(seq, []):
                cand[w] = self.uni[w]
        scores = {}
        if mode == "ratio":
            ratio = 1e10
            nmap = dict(nxt)
            if seq:  # JS: min over all prefix words; only bigram words can set it
                for w, b in nxt:
                    u = self.uni.get(w)
                    if u:
                        ratio = min(ratio, b / u)
            scores = dict(cand)
            for w, b in nmap.items():
                scores[w] = max(b / ratio, scores.get(w, 0))
        else:
            nt = self.next_total.get(prev, 0)
            l = lam if nt else 0.0
            for w, u in cand.items():
                scores[w] = (1 - l) * u / self.uni_total
            for w, b in nxt:
                if w not in scores:
                    scores[w] = (1 - l) * self.uni.get(w, 0) / self.uni_total
                scores[w] += l * b / nt
        exact, longer = [], []
        for w, s in scores.items():
            if self.code(w) == seq:
                exact.append((s, w))
            else:
                longer.append((s / divisor, w))
        exact.sort(key=lambda x: (-x[0], x[1]))
        longer.sort(key=lambda x: (-x[0], x[1]))
        rest = exact[1:] + longer[:n_longer]
        rest.sort(key=lambda x: (-x[0], x[1]))
        out = [w for _, w in exact[:1]] + [w for _, w in rest]
        self._ranked[memo_key] = out
        return out


# Same tokenizer as optimize_layout.py / get_sequences.py.
TOKEN = re.compile(
    r"(?:[A-Za-z]\.){2,}"
    r"|'(?:tis|twas|cause|em)\b"
    r"|[A-Za-z]+(?:['-][A-Za-z]+)*'?"
    r"|[.!?]"
    r"|[\"“](?=[A-Za-z'])",
    re.IGNORECASE,
)


def sentence_words(text):
    """Yield (word, starts_sentence); punctuation is dropped, "Mr." does not end a sentence."""
    text = text.replace("’", "'").replace("‘", "'")
    start, prev = True, None
    for tok in TOKEN.findall(text):
        if tok in ".!?":
            if not (tok == "." and prev is not None and prev.lower() in TITLES):
                start = True
            continue
        if tok in "\"“":
            start = True
            continue
        yield tok, start
        start, prev = False, tok


def read_sentences(path, every, offset, limit):
    """Tatoeba .tsv (id, lang, text) or one sentence per line."""
    n = 0
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f):
            parts = line.rstrip("\r\n").split("\t")
            text = parts[2] if len(parts) >= 3 else parts[-1]
            key = int(parts[0]) if len(parts) >= 3 and parts[0].isdigit() else lineno
            if every > 1 and key % every != offset:
                continue
            yield text
            n += 1
            if limit and n >= limit:
                return


def type_word(r, word, prev, setting, costs, bar):
    """(cost, keys, position or 0) of the cheapest way to enter word."""
    n_longer, divisor, mode, lam = setting
    c_space, c_bar, c_more = costs
    code = r.code(word)
    best = None
    for j in range(0, len(code) + 1):
        lst = r.rank(prev, code[:j], n_longer, divisor, mode, lam)
        try:
            pos = lst.index(word) + 1
        except ValueError:
            continue
        if j == 0:  # nothing typed: only a tap on the bar or the dropdown
            sel, k = (c_bar, 1) if pos <= bar else (c_more, 2)
        elif pos == 1:
            sel, k = c_space, 1
        elif pos <= bar:
            sel, k = c_bar, 1
        else:
            sel, k = c_more, 2
        if best is None or j + sel < best[0]:
            best = (j + sel, j + k, pos)
    return best


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--keyed", default=os.path.join(DATA_DIR, "curated", "en_keyed.json"))
    p.add_argument("--sentences", required=True, help="e.g. data/raw/tatoeba/eng_sentences.tsv")
    p.add_argument("--completions", type=int, nargs="+", default=[0, 1, 2, 3, 4, 5, 6],
                   help="longer words to show (default 0..6)")
    p.add_argument("--divisor", type=float, nargs="+", default=[8.0],
                   help="score divisor for longer words (en_rank's N, default 8)")
    p.add_argument("--score", choices=("ratio", "interp"), nargs="+", default=["ratio", "interp"])
    p.add_argument("--lam", type=float, default=0.7, help="bigram weight for --score interp")
    p.add_argument("--bar", type=int, default=3, help="candidates visible without the dropdown")
    p.add_argument("--cost-space", type=float, default=1.0)
    p.add_argument("--cost-bar", type=float, default=2.0)
    p.add_argument("--cost-more", type=float, default=4.0)
    p.add_argument("--every", type=int, default=1, help="use every Nth sentence by id")
    p.add_argument("--offset", type=int, default=0)
    p.add_argument("--limit", type=int, default=20000, help="max sentences (0 = all)")
    a = p.parse_args()

    r = Ranker(a.keyed)
    sents = list(read_sentences(a.sentences, a.every, a.offset, a.limit))
    costs = (a.cost_space, a.cost_bar, a.cost_more)
    settings = [(n, d, m, a.lam) for m in a.score for d in a.divisor for n in a.completions]
    print(f"{len(sents)} sentences, {len(r.uni)} words, bar {a.bar}, "
          f"costs space/bar/more {costs[0]:g}/{costs[1]:g}/{costs[2]:g}")
    print(f"\n{'score':<7} {'div':>5} {'longer':>6} {'KPL':>7} {'cost/let':>8} "
          f"{'slot 1':>7} {'bar':>6} {'dropdn':>7} {'early':>6} {'unknown':>8}")
    results = []
    for s in settings:
        keys = cost = letters = 0
        slot1 = in_bar = dropdown = early = words = unknown = 0
        t0 = time.time()
        r._ranked.clear()
        for sent in sents:
            prev = START
            for tok, starts in sentence_words(sent):
                if starts:
                    prev = START
                low = tok.lower().rstrip("'") if tok.lower() not in r.lower else tok.lower()
                word = r.lower.get(low)
                n = len(r.code(tok))
                letters += n
                words += 1
                if word is None:  # not in the word list: type it out, then space
                    unknown += 1
                    keys += n + 1
                    cost += n + 1
                    prev = low
                    continue
                c, k, pos = type_word(r, word, prev, s, costs, a.bar)
                keys += k
                cost += c
                slot1 += pos == 1
                in_bar += 2 <= pos <= a.bar
                dropdown += pos > a.bar
                early += k - (1 if pos <= a.bar else 2) < len(r.code(word))
                prev = low
        known = max(1, words - unknown)
        row = (s, keys / letters, cost / letters)
        results.append(row)
        print(f"{s[2]:<7} {s[1]:>5g} {s[0]:>6} {keys / letters:7.4f} {cost / letters:8.4f} "
              f"{100 * slot1 / known:6.1f}% {100 * in_bar / known:5.1f}% {100 * dropdown / known:6.1f}% "
              f"{100 * early / known:5.1f}% {100 * unknown / max(1, words):7.2f}%"
              f"   ({time.time() - t0:.0f}s)", flush=True)
    best = min(results, key=lambda x: x[2])
    print(f"\nlowest cost: --score {best[0][2]} --divisor {best[0][1]:g} --completions {best[0][0]} "
          f"(KPL {best[1]:.4f})")
    print("KPL = keypresses (letters, space, taps) per letter; cost/let uses the costs above.")
    print("slot 1 / bar / dropdn = where the word was picked (known words); "
          "early = picked before typing all its letters.")


if __name__ == "__main__":
    main()
