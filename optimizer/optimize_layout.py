#!/usr/bin/env python3
"""Find an English letter layout for the 10-key IME. Standard library only.

Keys: space, backspace, function, and K letter keys (K = 7; K = 8 is a what-if
for merging the function key away). Each letter key holds a group of letters.
The user presses one key per letter; the IME ranks every word with that key
sequence by P(word | previous word). Space takes the top word; the next ones
are tapped in the candidate bar (3 visible); past that the bar is expanded.

Selection cost per word (lower is better):
  rank 1          -> --cost-space (1)   press space
  rank 2..--bar   -> --cost-bar   (2)   reach up and tap the bar
  rank > --bar    -> --cost-more  (4)   expand the bar, then tap

Collision score (the default objective): every pair of words that share a
key sequence adds a penalty that is large only when BOTH words are common.
  --penalty min      pair penalty = min(count a, count b)     (default)
  --penalty product  pair penalty = count a * count b / total
  C0  collision score on word counts (no context). Fast; the search runs on it.
  C   collision score inside each context: a pair only counts when both words
      follow the same previous word (he/if rarely compete, that/what often do).
      Re-ranking and the final polish run on it.
Also reported, not optimized (unless --objective cost):
  J0/J  selection cost per word with the costs above, without/with context.

Usage:
  python optimize_layout.py pilot   # short runs: free vs alphabetical, K=7 and K=8
  python optimize_layout.py full --variant free --keys 7
  python optimize_layout.py full --variant hybrid --keys 7  # 6 alphabet runs + leftovers
  python optimize_layout.py exhaust --keys 7   # every alphabetical layout
  python optimize_layout.py kpl --layout "abcd efgh ..." --layout "..."
  python optimize_layout.py kpl-sentences --sentences eng_sentences.tsv --layout "..."
  python optimize_layout.py kpl-sweep --layout "abcd efgh ..."   # best threshold M
  python optimize_layout.py score --layout "abc def ghi jkl mno pqrs tuv wxyz"

Common options: --words data/unigrams.tsv --bigrams data/bigrams.tsv --seed 1
Run any mode with -h for all options.
"""
import argparse
import heapq
import itertools
import json
import math
import os
import random
import re
import string
import sys
import time

LETTERS = string.ascii_lowercase  # becomes a-z plus ' with --apostrophe on-key
N = 26


def set_alphabet(apostrophe):
    global LETTERS, N
    LETTERS = string.ascii_lowercase + ("'" if apostrophe == "on-key" else "")
    N = len(LETTERS)
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(HERE, "..", "data")


# ---------------------------------------------------------------- data

class Data:
    """Word list + bigrams, indexed by word id (ids sorted by count, high first)."""

    def __init__(self, words_path, bigrams_path, lam, apostrophe="own"):
        rows = {}
        with open(words_path, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) < 2:
                    continue
                form, count = parts[0], int(parts[1])
                key = form.lower()
                # ' and - share one key, so they are the same symbol in a code
                keep = string.ascii_lowercase + ("" if apostrophe == "strip" else "'")
                letters = "".join(ch for ch in key.replace("-", "'") if ch in keep)
                if not letters.strip("'"):
                    continue
                if key in rows:  # same word twice: add counts, keep first form
                    rows[key][1] += count
                else:
                    rows[key] = [form, count, letters]
        items = sorted(rows.items(), key=lambda kv: (-kv[1][1], kv[0]))
        self.form = [v[0] for _, v in items]
        self.uni = [v[1] for _, v in items]
        self.letters = [v[2] for _, v in items]
        self.id = {k: i for i, (k, _) in enumerate(items)}
        self.uni_total = sum(self.uni)
        self.joined = "\n".join(self.letters)
        self.n = len(self.form)

        # contexts: list of (total count, {word id: count})
        self.contexts = []
        self.ctx_index = {}  # previous word (lowercase, "<s>" = sentence start) -> context
        self.bigram_total = 0
        skipped = 0
        with open(bigrams_path, encoding="utf-8") as f:
            for line in f:
                parts = line.rstrip("\r\n").split("\t")
                if len(parts) < 2:
                    continue
                nxt = {}
                for pair in parts[1:]:
                    word, _, cnt = pair.rpartition(":")
                    if not word:
                        continue
                    wid = self.id.get(word.lower())
                    if wid is None:
                        skipped += 1
                        continue
                    nxt[wid] = nxt.get(wid, 0) + int(cnt)
                total = sum(nxt.values())
                if total:
                    self.ctx_index[parts[0].lower()] = len(self.contexts)
                    self.contexts.append((total, nxt))
                    self.bigram_total += total
        self.lam = lam
        self.uni_p = [(1 - lam) * c / self.uni_total for c in self.uni]
        print(f"loaded {self.n} words, {len(self.contexts)} contexts, "
              f"{self.bigram_total} bigram tokens ({skipped} pairs with unknown words skipped)",
              file=sys.stderr)


# ---------------------------------------------------------------- layouts

def groups_of(keymap, k):
    g = [""] * k
    for i, key in enumerate(keymap):
        g[key] += LETTERS[i]
    return g


def layout_str(keymap, k):
    return " ".join(groups_of(keymap, k))


def canon(keymap, k):
    return tuple(sorted(groups_of(keymap, k)))


def parse_layout(text):
    """Returns (keymap, number of keys, key holding the apostrophe or None)."""
    groups = text.split()
    keymap = [None] * N
    apos = None
    for key, grp in enumerate(groups):
        for ch in grp.lower().replace("-", "'"):
            if ch == "'" and "'" not in LETTERS:
                apos = key
                continue
            keymap[LETTERS.index(ch)] = key
    if None in keymap:
        missing = "".join(LETTERS[i] for i, v in enumerate(keymap) if v is None)
        sys.exit(f"layout is missing letters: {missing}")
    return keymap, len(groups), apos


def cuts_to_keymap(cuts):
    """Cut points (sorted, in 1..25) -> keymap of consecutive letter runs."""
    keymap, key, edges = [], 0, set(cuts)
    for i in range(N):
        if i in edges:
            key += 1
        keymap.append(key)
    return keymap


def even_alpha(k):
    sizes = [N // k + (1 if i < N % k else 0) for i in range(k)]
    cuts, pos = [], 0
    for s in sizes[:-1]:
        pos += s
        cuts.append(pos)
    return cuts


def random_free(k, rng, max_per_key):
    while True:
        keymap = list(range(k)) + [rng.randrange(k) for _ in range(N - k)]
        rng.shuffle(keymap)
        if not max_per_key or max(keymap.count(x) for x in range(k)) <= max_per_key:
            return keymap


def random_cuts(k, rng, max_per_key):
    while True:
        cuts = sorted(rng.sample(range(1, N), k - 1))
        if ok_cuts(cuts, max_per_key):
            return cuts


def ok_cuts(cuts, max_per_key):
    if not max_per_key:
        return True
    edges = [0] + cuts + [N]
    return all(b - a <= max_per_key for a, b in zip(edges, edges[1:]))


# ---------------------------------------------------------------- scoring

class Scorer:
    def __init__(self, data, bar, c_space, c_bar, c_more, penalty="min", objective="collision"):
        self.d = data
        self.bar = bar
        self.c = (c_space, c_bar, c_more)
        self.penalty = penalty
        self.objective = objective
        self.apos_key = None  # None: the apostrophe has its own key (never collides)

    def fast(self, keymap):
        """Search score (lower is better)."""
        return self.c0(keymap) if self.objective == "collision" else self.j0(keymap)

    def slow(self, keymap):
        """Polish score (lower is better)."""
        return self.full(keymap)["C" if self.objective == "collision" else "J"]

    def c0(self, keymap):
        """Collision score on word counts: sum of pair penalties, per word token."""
        seen = {}
        total = 0.0
        get = seen.get
        if self.penalty == "min":
            # words come most common first, so a new word is the smaller of
            # every pair it forms with the words already in its group
            for code, cnt in zip(self.codes(keymap), self.d.uni):
                r = get(code, 0)
                if r:
                    total += cnt * r
                seen[code] = r + 1
            return total / self.d.uni_total
        for code, cnt in zip(self.codes(keymap), self.d.uni):
            s = get(code, 0)
            if s:
                total += cnt * s
            seen[code] = s + cnt
        return total / self.d.uni_total ** 2

    def ctx_collisions(self, codes):
        """Collision score inside each context, per bigram token."""
        total = 0.0
        prod = self.penalty == "product"
        for ctx_total, nxt in self.d.contexts:
            buckets = {}
            for w, cnt in nxt.items():
                buckets.setdefault(codes[w], []).append(cnt)
            for b in buckets.values():
                if len(b) < 2:
                    continue
                if prod:
                    s = sum(b)
                    total += (s * s - sum(x * x for x in b)) / 2 / ctx_total
                else:
                    b.sort(reverse=True)
                    total += sum(x * i for i, x in enumerate(b))
        return total / self.d.bigram_total

    def codes(self, keymap):
        table = {ord(LETTERS[i]): chr(48 + key) for i, key in enumerate(keymap)}
        if self.apos_key is not None:
            table[ord("'")] = chr(48 + self.apos_key)
        return self.d.joined.translate(table).split("\n")

    def j0(self, keymap):
        """Unigram proxy: average selection cost per word token, no context."""
        c_space, c_bar, c_more = self.c
        bar = self.bar
        seen = {}
        extra = 0.0
        get = seen.get
        for code, cnt in zip(self.codes(keymap), self.d.uni):
            r = get(code, 0)  # words before this one in the same group
            if r:
                extra += cnt * ((c_bar if r < bar else c_more) - c_space)
            seen[code] = r + 1
        return c_space + extra / self.d.uni_total

    def full(self, keymap, costs=None, collisions=False):
        """Full score J with context. Returns dict of metrics."""
        c_space, c_bar, c_more = costs or self.c
        bar, d = self.bar, self.d
        codes = self.codes(keymap)
        groups = {}
        for i, code in enumerate(codes):
            groups.setdefault(code, []).append(i)
        lam, uni_p = d.lam, d.uni_p
        top1 = topbar = 0
        cost = 0.0
        pairs = {} if collisions else None
        for total, nxt in d.contexts:
            scale = lam / total
            for w, cnt in nxt.items():
                g = groups[codes[w]]
                rank = 1
                if len(g) > 1:
                    sw = scale * cnt + uni_p[w]
                    best, best_s = None, -1.0
                    for x in g:
                        if x == w:
                            continue
                        sx = scale * nxt.get(x, 0) + uni_p[x]
                        if sx > sw or (sx == sw and x < w):
                            rank += 1
                            if collisions:
                                if sx > best_s:
                                    best, best_s = x, sx
                            elif rank > bar:
                                break
                    if collisions and best is not None:
                        key = (best, w)
                        pairs[key] = pairs.get(key, 0) + cnt
                if rank == 1:
                    top1 += cnt
                    cost += cnt * c_space
                elif rank <= bar:
                    topbar += cnt
                    cost += cnt * c_bar
                else:
                    cost += cnt * c_more
        n = d.bigram_total
        out = {"J": cost / n, "top1": top1 / n, "topbar": (top1 + topbar) / n,
               "C": self.ctx_collisions(codes)}
        if collisions:
            out["pairs"] = pairs
        return out


# ---------------------------------------------------------------- search

def neighbors_free(keymap, k, max_per_key):
    sizes = [keymap.count(x) for x in range(k)]
    for i in range(N):
        if sizes[keymap[i]] == 1:
            continue
        for key in range(k):
            if key != keymap[i] and (not max_per_key or sizes[key] < max_per_key):
                m = keymap[:]
                m[i] = key
                yield m
    for i in range(N):
        for j in range(i + 1, N):
            if keymap[i] != keymap[j]:
                m = keymap[:]
                m[i], m[j] = m[j], m[i]
                yield m


def neighbors_alpha(cuts, max_per_key):
    for idx in range(len(cuts)):
        for step in (-1, 1):
            c = cuts[:]
            c[idx] += step
            lo = c[idx - 1] if idx else 0
            hi = c[idx + 1] if idx + 1 < len(c) else N
            if lo < c[idx] < hi and ok_cuts(c, max_per_key):
                yield c


def random_move_free(keymap, k, rng, max_per_key):
    while True:
        m = keymap[:]
        if rng.random() < 0.5:
            i = rng.randrange(N)
            key = rng.randrange(k)
            if key == m[i] or m.count(m[i]) == 1:
                continue
            m[i] = key
        else:
            i, j = rng.sample(range(N), 2)
            if m[i] == m[j]:
                continue
            m[i], m[j] = m[j], m[i]
        if not max_per_key or m.count(m[i]) <= max_per_key:
            return m


def random_move_alpha(cuts, rng, max_per_key):
    for _ in range(1000):
        c = cuts[:]
        idx = rng.randrange(len(c))
        c[idx] += rng.choice((-2, -1, 1, 2))
        lo = c[idx - 1] if idx else 0
        hi = c[idx + 1] if idx + 1 < len(c) else N
        if lo < c[idx] < hi and ok_cuts(c, max_per_key):
            return c
    return cuts


def valid_hybrid(keymap, k, skip=False):
    """Keys 0..k-2 each hold one unbroken alphabet run; key k-1 holds the rest.

    skip=True ("hybrid-skip"): runs only need to be unbroken once the
    leftover key's letters are taken out (mnp is a run when o is a leftover)."""
    last = k - 1
    if last not in keymap:
        return False
    seen = set()
    prev = None
    for key in keymap:
        if skip and key == last:
            continue
        if key != prev:
            if key != last:
                if key in seen:
                    return False  # this run was broken by another key
                seen.add(key)
            prev = key
    return len(seen) == last


def random_hybrid(k, rng, max_per_key):
    """Uniform random hybrid layout: k-1 runs with gaps between; gaps go to the last key."""
    runs = k - 1
    while True:
        # split 26 into runs lengths (>= 1) and runs + 1 gaps (>= 0)
        cuts = sorted(rng.sample(range(1, N + runs + 1), 2 * runs))
        parts = [b - a for a, b in zip([0] + cuts, cuts + [N + runs + 1])]
        gaps = [parts[i] - 1 for i in range(0, len(parts), 2)]
        lens = [parts[i] for i in range(1, len(parts), 2)]
        if sum(gaps) == 0:
            continue
        keymap = []
        for i in range(runs):
            keymap += [runs] * gaps[i] + [i] * lens[i]
        keymap += [runs] * gaps[runs]
        if not max_per_key or max(keymap.count(x) for x in range(k)) <= max_per_key:
            return keymap


def random_move_hybrid(keymap, k, rng, max_per_key, skip=False):
    for _ in range(5000):
        m = random_move_free(keymap, k, rng, max_per_key)
        if valid_hybrid(m, k, skip):
            return m
    return keymap


def anneal(scorer, variant, k, moves, rng, max_per_key, checkpoints=10, label=""):
    """Simulated annealing on the fast score (C0, or J0 with --objective cost). Returns (best keymap, best J0, curve)."""
    if variant == "free":
        state = random_free(k, rng, max_per_key)
        to_map = lambda s: s
        move = lambda s: random_move_free(s, k, rng, max_per_key)
    elif variant in ("hybrid", "hybrid-skip"):
        skip = variant == "hybrid-skip"
        state = random_hybrid(k, rng, max_per_key)
        to_map = lambda s: s
        move = lambda s: random_move_hybrid(s, k, rng, max_per_key, skip)
    else:
        state = random_cuts(k, rng, max_per_key)
        to_map = cuts_to_keymap
        move = lambda s: random_move_alpha(s, rng, max_per_key)

    cur = scorer.fast(to_map(state))
    # starting temperature: average size of a worsening move
    deltas = []
    for _ in range(30):
        dlt = scorer.fast(to_map(move(state))) - cur
        if dlt > 0:
            deltas.append(dlt)
    t0 = (sum(deltas) / len(deltas)) if deltas else 1e-3
    t_end = t0 * 1e-3
    best_state, best = state, cur
    curve, every = [], max(1, moves // checkpoints)
    start = time.time()
    for step in range(1, moves + 1):
        t = t0 * (t_end / t0) ** (step / moves)
        cand = move(state)
        val = scorer.fast(to_map(cand))
        if val <= cur or rng.random() < math.exp((cur - val) / t):
            state, cur = cand, val
            if cur < best:
                best_state, best = state, cur
        if step % every == 0:
            curve.append(round(best, 5))
            print(f"\r  {label} step {step}/{moves}  best {best:.5f}  "
                  f"({time.time() - start:.0f}s)", end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    return to_map(best_state), best, curve, best_state


def hill_climb_full(scorer, variant, k, state, max_per_key, screen, max_rounds):
    """Polish on the slow score: pre-screen all neighbours on the fast one."""
    to_map = cuts_to_keymap if variant == "alpha" else (lambda s: s)
    cur = scorer.slow(to_map(state))
    for rnd in range(max_rounds):
        if variant == "free":
            nbrs = list(neighbors_free(state, k, max_per_key))
        elif variant in ("hybrid", "hybrid-skip"):
            skip = variant == "hybrid-skip"
            nbrs = [m for m in neighbors_free(state, k, max_per_key) if valid_hybrid(m, k, skip)]
        else:
            nbrs = list(neighbors_alpha(state, max_per_key))
        nbrs.sort(key=lambda s: scorer.fast(to_map(s)))
        improved = False
        for cand in nbrs[:screen]:
            val = scorer.slow(to_map(cand))
            if val < cur - 1e-9:
                state, cur, improved = cand, val, True
                break
        print(f"  hill-climb round {rnd + 1}: {cur:.5f}", file=sys.stderr)
        if not improved:
            break
    return state, cur


# ---------------------------------------------------------------- reports

def fmt_row(name, keymap, k, scorer, full=None):
    full = full or scorer.full(keymap)
    return (f"{name:<22} {scorer.c0(keymap):8.5f} {full['C']:8.5f} {scorer.j0(keymap):7.4f} "
            f"{full['J']:7.4f} {100 * full['top1']:6.2f}% {100 * full['topbar']:6.2f}%   "
            f"{layout_str(keymap, k)}")


def fmt_metrics(name, c0, m, j0=None):
    c0s = f"{c0:8.5f}" if c0 is not None else " " * 8
    j0s = f"{j0:7.4f}" if j0 is not None else " " * 7
    return (f"{name:<22} {c0s} {m['C']:8.5f} {j0s} {m['J']:7.4f} "
            f"{100 * m['top1']:6.2f}% {100 * m['topbar']:6.2f}%")


HEADER = (f"{'layout':<22} {'C0':>8} {'C':>8} {'J0':>7} {'J':>7} {'top-1':>7} {'top-3':>7}   keys")


def baselines(scorer, k, rng, n_random=5):
    rows = []
    if k == 8:
        t9, _, _ = parse_layout("abc def ghi jkl mno pqrs tuv wxyz")
        rows.append(("phone T9", t9))
    rows.append(("even alphabetical", cuts_to_keymap(even_alpha(k))))
    rand = [random_free(k, rng, 0) for _ in range(n_random)]
    fulls = [scorer.full(m) for m in rand]
    avg = {key: sum(f[key] for f in fulls) / n_random for key in ("J", "top1", "topbar", "C")}
    avg["C0"] = sum(scorer.c0(m) for m in rand) / n_random
    avg["J0"] = sum(scorer.j0(m) for m in rand) / n_random
    return rows, avg


def floor_score(scorer):
    """Cost with one key per letter: collisions no layout can remove (its/it's)."""
    return scorer.full(list(range(N)))


def cmd_pilot(a, data, scorer):
    rng = random.Random(a.seed)
    results = []
    print(HEADER.replace("layout", "variant/start"))
    for k in a.keys:
        for variant in a.variants:
            for s in range(a.starts):
                label = f"{variant} K={k} start {s + 1}"
                keymap, best, curve, _ = anneal(scorer, variant, k, a.moves, rng,
                                                a.max_per_key, label=label)
                full = scorer.full(keymap)
                results.append({"variant": variant, "keys": k, "start": s + 1,
                                "search_score": best, "C0": scorer.c0(keymap), "C": full["C"],
                                "J0": scorer.j0(keymap), "J": full["J"], "top1": full["top1"],
                                "topbar": full["topbar"], "curve": curve,
                                "layout": layout_str(keymap, k)})
                print(fmt_row(label, keymap, k, scorer, full), flush=True)

    print("\nsummary (mean over starts, spread = max - min)")
    print(f"{'variant':<12} {'K':>2} {'C0 mean':>9} {'C0 spread':>10} {'C mean':>9} {'C spread':>9} {'top-1 mean':>11}")
    for k in a.keys:
        for variant in a.variants:
            rs = [r for r in results if r["variant"] == variant and r["keys"] == k]
            c0s = [r["C0"] for r in rs]
            cs = [r["C"] for r in rs]
            t1 = sum(r["top1"] for r in rs) / len(rs)
            print(f"{variant:<12} {k:>2} {sum(c0s) / len(c0s):9.5f} {max(c0s) - min(c0s):10.5f} "
                  f"{sum(cs) / len(cs):9.5f} {max(cs) - min(cs):9.5f} {100 * t1:10.2f}%")
    print("\nbest search score over the run, per start (flat at the end = run was long enough):")
    for r in results:
        print(f"  {r['variant']:<5} K={r['keys']} s{r['start']}: " + " ".join(f"{v:.5f}" for v in r["curve"]))

    print("\nbaselines")
    print(HEADER)
    fl = floor_score(scorer)
    print(fmt_metrics("floor (1 key each)", scorer.c0(list(range(N))), fl, scorer.j0(list(range(N)))))
    for k in a.keys:
        rows, ravg = baselines(scorer, k, rng)
        for name, m in rows:
            print(fmt_row(f"{name} K={k}", m, k, scorer))
        print(fmt_metrics(f"random avg K={k}", ravg["C0"], ravg, ravg["J0"]))

    with open(a.out, "w", encoding="utf-8") as f:
        json.dump({"settings": settings(a), "runs": results}, f, indent=1)
    print(f"\nsaved {a.out}")


def cmd_full(a, data, scorer):
    rng = random.Random(a.seed)
    k, variant = a.keys[0], a.variant
    found = {}
    for s in range(a.starts):
        keymap, best, _, state = anneal(scorer, variant, k, a.moves, rng, a.max_per_key,
                                        label=f"{variant} K={k} start {s + 1}/{a.starts}")
        c = canon(keymap, k)
        if c not in found or best < found[c][0]:
            found[c] = (best, state)
    print(f"{len(found)} distinct layouts from {a.starts} starts", file=sys.stderr)

    to_map = cuts_to_keymap if variant == "alpha" else (lambda s: s)
    top = sorted(found.values(), key=lambda x: x[0])[:a.rerank]
    scored = []
    for _, state in top:
        scored.append((scorer.slow(to_map(state)), state))
    scored.sort(key=lambda x: x[0])

    polished = []
    for _, state in scored[:a.polish]:
        st, j = hill_climb_full(scorer, variant, k, state, a.max_per_key, a.screen, a.rounds)
        polished.append((j, st))
    polished.sort(key=lambda x: x[0])
    winner = to_map(polished[0][1])
    report(a, data, scorer, winner, [to_map(st) for _, st in polished[1:]], k, rng)


def cmd_exhaust(a, data, scorer):
    """Score every alphabetical layout on C0, then re-rank the best on C."""
    rng = random.Random(a.seed)
    k = a.keys[0]
    total = math.comb(25, k - 1)
    heap = []  # (-score, cuts): the a.rerank best layouts on the fast score
    start = time.time()
    done = 0
    for cuts in itertools.combinations(range(1, N), k - 1):
        done += 1
        cuts = list(cuts)
        if not ok_cuts(cuts, a.max_per_key):
            continue
        v = scorer.fast(cuts_to_keymap(cuts))
        if len(heap) < a.rerank:
            heapq.heappush(heap, (-v, cuts))
        elif v < -heap[0][0]:
            heapq.heapreplace(heap, (-v, cuts))
        if done % 2000 == 0:
            el = time.time() - start
            print(f"\r  {done}/{total} layouts  best {-max(heap)[0]:.5f}  "
                  f"{el:.0f}s elapsed, ~{el * (total - done) / done:.0f}s left",
                  end="", file=sys.stderr, flush=True)
    print(file=sys.stderr)
    fast_sorted = sorted((-nv, c) for nv, c in heap)
    print(f"re-scoring the best {len(fast_sorted)} on the context score", file=sys.stderr)
    slow_sorted = sorted(((scorer.slow(cuts_to_keymap(c)), i, c)
                          for i, (_, c) in enumerate(fast_sorted)))
    print(f"\ntop 10 alphabetical layouts by the context score (rank on the fast score in brackets)")
    for val, i, c in slow_sorted[:10]:
        print(f"  {val:.6f}  [{i + 1:>3}]  {layout_str(cuts_to_keymap(c), k)}")
    winner = cuts_to_keymap(slow_sorted[0][2])
    report(a, data, scorer, winner, [cuts_to_keymap(c) for _, _, c in slow_sorted[1:3]], k, rng)


def report(a, data, scorer, winner, runners, k, rng):
    full = scorer.full(winner, collisions=True)
    print("\nresults")
    print(HEADER)
    print(fmt_row("winner", winner, k, scorer, full))
    for i, m in enumerate(runners, 2):
        print(fmt_row(f"runner-up {i}", m, k, scorer))
    fl = floor_score(scorer)
    print(fmt_metrics("floor (1 key each)", scorer.c0(list(range(N))), fl, scorer.j0(list(range(N)))))
    rows, ravg = baselines(scorer, k, rng)
    for name, m in rows:
        print(fmt_row(name, m, k, scorer))
    print(fmt_metrics("random avg", ravg["C0"], ravg, ravg["J0"]))

    print("\nrobustness: winner vs even alphabetical under the other pair penalty (C0, C)")
    even = cuts_to_keymap(even_alpha(k))
    keep = scorer.penalty
    for pen in ("min", "product"):
        scorer.penalty = pen
        print(f"  {pen:<8} winner C0 {scorer.c0(winner):.6f} C {scorer.full(winner)['C']:.6f}   "
              f"even alpha C0 {scorer.c0(even):.6f} C {scorer.full(even)['C']:.6f}")
    scorer.penalty = keep

    print("\nrobustness: winner vs even alphabetical under other tap costs (J)")
    even = cuts_to_keymap(even_alpha(k))
    for costs in ((1, 1.5, 3), (1, 2, 4), (1, 3, 6)):
        w, e = scorer.full(winner, costs)["J"], scorer.full(even, costs)["J"]
        print(f"  space/bar/more = {costs}: winner {w:.4f}  even alpha {e:.4f}")

    print_collisions(data, scorer, winner, full)

    out = {"settings": settings(a), "keys": groups_of(winner, k),
           "letter_to_key": {LETTERS[i]: key for i, key in enumerate(winner)},
           "metrics": {"C0": scorer.c0(winner), "C": full["C"],
                       "J0": scorer.j0(winner), "J": full["J"], "top1": full["top1"],
                       "top3": full["topbar"]}}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(f"\nsaved {a.out}")


def cmd_score(a, data, scorer):
    keymap, k, apos = parse_layout(a.layout)
    if apos is not None:
        if a.apostrophe == "strip":
            sys.exit("the layout puts ' on a key; drop --apostrophe strip to score it")
        scorer.apos_key = apos
    full = scorer.full(keymap, collisions=True)
    print(HEADER)
    print(fmt_row("given", keymap, k, scorer, full))
    print_collisions(data, scorer, keymap, full)


class KPL:
    """Keystrokes per letter with prefix completion.

    After each key press the bar shows: slot 1 = best word whose code is exactly
    the keys typed so far, slot 2 = best longer word starting with those keys
    (the completion), slots 3.. = the next exact words; with no completion shown
    the exact words fill slots 2.. instead. The completion is only shown when it
    is at least `mult` times as likely as the runner-up completion. Tapping a
    bar word or pressing space commits the word with its trailing space. For
    each word the user takes the cheapest way (by --cost-* weights): type it
    all and press space / tap, or tap it in slot 2 as soon as it appears there.
    Every completion shown that is NOT the wanted word adds `wrong_cost` to the
    cost (the price of reading a useless suggestion).

    order="sorted" (default, as in the old prototype): take the `n_longer` best
    longer words, divide their scores by `divisor`, put the most likely exact
    word in slot 1, then sort all other candidates (exact and longer) by score.
    order="ratio": slot 2 holds the best longer word only if it is `mult` times
    as likely as the runner-up longer word; exact words fill the other slots.
    """

    def __init__(self, data, scorer, keymap, mult=1.0, wrong_cost=0.0,
                 order="sorted", divisor=1.2, per_letter=False, n_longer=3):
        self.d, self.mult, self.wrong_cost = data, mult, wrong_cost
        self.order, self.divisor, self.per_letter = order, divisor, per_letter
        self.n_longer = n_longer
        self.c = scorer.c
        self.bar = scorer.bar
        self.codes = scorer.codes(keymap)
        self.groups, self.top_uni = {}, {}
        for i, code in enumerate(self.codes):  # ids run from most to least common
            self.groups.setdefault(code, []).append(i)
            for j in range(1, len(code)):
                t = self.top_uni.setdefault(code[:j], [])
                if len(t) < 4:
                    t.append(i)
        self.cache = {}

    def _bar(self, pre, score, top):
        """The full candidate list after typing `pre` (slot 1 first)."""
        exact = sorted(self.groups.get(pre, ()), key=lambda x: (-score(x), x))
        longer = sorted(set(top(pre)), key=lambda x: (-score(x), x))
        if self.order == "ratio":
            comp = None
            if longer and (len(longer) == 1 or
                           score(longer[0]) >= self.mult * score(longer[1])):
                comp = longer[0]
            return exact[:1] + ([comp] if comp is not None else []) + exact[1:]
        # sorted: 1) take the best longer words, 2) divide their scores by N,
        # 3) slot 1 = most likely exact word, 4) sort everything else together
        longer = longer[:self.n_longer]
        n, codes, d = len(pre), self.codes, self.divisor
        if self.per_letter:
            pen = lambda x: score(x) / d ** (len(codes[x]) - n)
        else:
            pen = lambda x: score(x) / d
        rest = [(score(x), x) for x in exact[1:]] + [(pen(x), x) for x in longer]
        rest.sort(key=lambda v: (-v[0], v[1]))
        return exact[:1] + [x for _, x in rest]

    def predictor(self, ctx):
        """(score, bar) for a context index, or None = word counts only."""
        if ctx in self.cache:
            return self.cache[ctx]
        memo = {}
        if ctx is None:
            score = self.d.uni.__getitem__
            top = lambda pre: self.top_uni.get(pre, [])
        else:
            total, nxt = self.d.contexts[ctx]
            scale, uni_p = self.d.lam / total, self.d.uni_p
            score = lambda x: scale * nxt.get(x, 0) + uni_p[x]
            top_ctx = {}
            for x, c in nxt.items():
                code = self.codes[x]
                sx = scale * c + uni_p[x]
                for j in range(1, len(code)):
                    top_ctx.setdefault(code[:j], []).append((sx, x))
            for t in top_ctx.values():
                if len(t) > 4:
                    t.sort(key=lambda v: (-v[0], v[1]))
                    del t[4:]
            top = lambda pre: self.top_uni.get(pre, []) + [x for _, x in top_ctx.get(pre, [])]

        def bar(pre):
            if pre not in memo:
                memo[pre] = self._bar(pre, score, top)
            return memo[pre]

        self.cache[ctx] = (score, bar)
        return self.cache[ctx]

    def word(self, w, pred):
        """Cheapest way to enter word w. Returns (cost, keys, completed early?,
        wrong suggestions seen, letters).

        After j keys the user can commit w if it is in the list: space for
        slot 1, a tap for slots 2..bar, expand + tap beyond. A key press state
        where longer words are visible but w is not counts as one wrong
        suggestion seen (cost --wrong-cost)."""
        _, bar = pred
        c_space, c_bar, c_more = self.c
        code = self.codes[w]
        n = len(code)
        codes, vis = self.codes, self.bar
        best = None
        wrong = 0
        for j in range(1, n + 1):
            lst = bar(code[:j])
            try:
                pos = lst.index(w) + 1
            except ValueError:
                pos = 0
            if pos:
                if pos == 1:
                    sel, k = c_space, 1
                elif pos <= vis:
                    sel, k = c_bar, 1
                else:
                    sel, k = c_more, 2
                cost = j + sel + wrong * self.wrong_cost
                if best is None or cost < best[0]:
                    best = (cost, j + k, j < n, wrong, n)
            if j < n and (pos == 0 or pos > vis):
                if any(len(codes[x]) > j for x in lst[:vis]):
                    wrong += 1
        return best


def new_stats():
    return {"keys": 0.0, "cost": 0.0, "letters": 0.0, "tokens": 0.0, "completed": 0.0,
            "over": 0.0, "wrong": 0.0, "by_len": {}}


def add_stats(st, res, cnt=1):
    cost, keys, done, wrong, n = res
    st["keys"] += cnt * keys
    st["cost"] += cnt * cost
    st["letters"] += cnt * n
    st["tokens"] += cnt
    st["completed"] += cnt * done
    st["wrong"] += cnt * wrong
    st["over"] += cnt * (keys > n)
    b = st["by_len"].setdefault(min(n, 8), [0.0, 0.0])
    b[0] += cnt * keys
    b[1] += cnt * n


def kpl_eval(data, scorer, keymap, context=True, **kw):
    """KPL over the bigram tokens (context=True) or the word list (False)."""
    k = KPL(data, scorer, keymap, **kw)
    st = new_stats()
    if not context:
        pred = k.predictor(None)
        for w, cnt in enumerate(data.uni):
            add_stats(st, k.word(w, pred), cnt)
        return st
    for ci, (_, nxt) in enumerate(data.contexts):
        pred = k.predictor(ci)
        for w, cnt in nxt.items():
            add_stats(st, k.word(w, pred), cnt)
        k.cache.pop(ci, None)  # each context is used once here
    return st


# Same tokenizer as get_sequences.py, so sentence words match the word list.
TOKEN = re.compile(
    r"(?:[A-Za-z]\.){2,}"
    r"|'(?:tis|twas|cause|em)\b"
    r"|[A-Za-z]+(?:['-][A-Za-z]+)*'?"
    r"|[.!?]"
    r"|[\"\u201c](?=[A-Za-z'])",
    re.IGNORECASE,
)
TITLES = {"mr", "mrs", "ms", "dr", "st", "jr", "sr", "vs"}


def sentence_words(text):
    """Yield (word, starts_sentence) for one line of text; punctuation is dropped."""
    text = text.replace("\u2019", "'").replace("\u2018", "'")
    start, prev = True, None
    for tok in TOKEN.findall(text):
        if tok in ".!?":
            if not (tok == "." and prev is not None and prev.lower() in TITLES):
                start = True
            continue
        if tok in "\"\u201c":
            start = True
            continue
        yield tok, start
        start, prev = False, tok


def read_sentences(path, lang, every, offset, limit):
    """Tatoeba .tsv (id, lang, text) or a plain file with one sentence per line."""
    n = 0
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f):
            parts = line.rstrip("\r\n").split("\t")
            if len(parts) >= 3:
                sid, lng, text = parts[0], parts[1], parts[2]
                if lang and lng != lang:
                    continue
                key = int(sid) if sid.isdigit() else lineno
            else:
                text, key = parts[-1], lineno
            if every > 1 and key % every != offset:
                continue
            yield text
            n += 1
            if limit and n >= limit:
                return


def pct(values, q):
    if not values:
        return float("nan")
    i = min(len(values) - 1, max(0, int(round(q * (len(values) - 1)))))
    return values[i]


def cmd_kpl_sentences(a, data, scorer):
    print(f"sentences: {a.sentences}"
          + (f" (every {a.every}th by id, offset {a.offset})" if a.every > 1 else "")
          + (f", first {a.limit}" if a.limit else ""))
    print(f"{describe_slot2(a)}; wrong completion cost "
          f"{a.wrong_cost}; unknown words cost letters + 1 + {a.oov_cost}")
    results = []
    for text in a.layout:
        keymap = setup_layout(a, scorer, text)
        k = KPL(data, scorer, keymap, **kpl_kw(a))
        no_ctx = k.predictor(None)
        st = new_stats()
        per_sent = []
        oov_tokens = tokens = sents = oov_sents = 0
        start = time.time()
        for sent in read_sentences(a.sentences, a.lang, a.every, a.offset, a.limit):
            s_keys = s_letters = 0
            has_oov = False
            prev = "<s>"
            for word, starts in sentence_words(sent):
                if starts:
                    prev = "<s>"
                low = word.lower()
                w = data.id.get(low)
                if w is None and low.endswith("'"):  # closing quote, not a possessive
                    low = low[:-1]
                    w = data.id.get(low)
                tokens += 1
                if w is None:
                    has_oov = True
                    oov_tokens += 1
                    n = sum(1 for ch in low if ch in LETTERS or ch in "'-")
                    s_keys += n + 1 + a.oov_cost
                    s_letters += n
                    prev = low
                    continue
                ctx = data.ctx_index.get(prev) if not a.no_context else None
                res = k.word(w, k.predictor(ctx) if ctx is not None else no_ctx)
                add_stats(st, res)
                s_keys += res[1]
                s_letters += res[4]
                prev = low
            if not s_letters:
                continue
            sents += 1
            oov_sents += has_oov
            if not (has_oov and a.skip_oov):
                per_sent.append(s_keys / s_letters)
            if sents % 20000 == 0:
                print(f"\r  {text}: {sents} sentences ({time.time() - start:.0f}s)",
                      end="", file=sys.stderr, flush=True)
        print(file=sys.stderr)
        per_sent.sort()
        results.append((text, st, per_sent, tokens, oov_tokens, sents, oov_sents))

    print(f"\n{'layout':<40} {'KPL':>6} {'mean':>6} {'p10':>6} {'p50':>6} {'p90':>6} "
          f"{'<1':>6} {'<0.9':>6} {'completed':>9} {'unknown':>8}")
    for text, st, ps, tokens, oov, sents, oov_s in results:
        lt1 = 100 * sum(1 for v in ps if v < 1) / max(1, len(ps))
        lt09 = 100 * sum(1 for v in ps if v < 0.9) / max(1, len(ps))
        mean = sum(ps) / max(1, len(ps))
        print(f"{text:<40} {st['keys'] / max(1, st['letters']):6.3f} {mean:6.3f} "
              f"{pct(ps, .1):6.3f} {pct(ps, .5):6.3f} {pct(ps, .9):6.3f} {lt1:5.1f}% {lt09:5.1f}% "
              f"{100 * st['completed'] / max(1, st['tokens']):8.1f}% {100 * oov / max(1, tokens):7.2f}%")
    print("\nKPL = all keystrokes / all letters over known words (spaces and taps count as keys).")
    print("mean/p10/p50/p90 = per-sentence KPL (unknown words included at their cost"
          + (", sentences with unknown words skipped" if a.skip_oov else "") + ").")
    print("<1, <0.9 = share of sentences under that KPL. Punctuation and capitals are not counted.")
    print("\nKPL by word length")
    print(f"{'layout':<40} " + " ".join(f"{('len ' + str(n) + ('+' if n == 8 else '')):>7}" for n in range(1, 9)))
    for text, st, *_ in results:
        cells = []
        for n in range(1, 9):
            b = st["by_len"].get(n)
            cells.append(f"{b[0] / b[1]:7.3f}" if b else " " * 7)
        print(f"{text:<40} " + " ".join(cells))


def kpl_row(text, st_c, st_u):
    return (f"{text:<40} {st_c['keys'] / st_c['letters']:8.3f} {st_u['keys'] / st_u['letters']:10.3f} "
            f"{st_c['cost'] / st_c['letters']:11.3f} {100 * st_c['completed'] / st_c['tokens']:8.1f}% "
            f"{st_c['wrong'] / st_c['tokens']:7.2f}")


KPL_HEADER = (f"{'layout':<40} {'KPL ctx':>8} {'KPL no-ctx':>10} {'cost/letter':>11} "
              f"{'completed':>9} {'wrong/w':>7}")


def setup_layout(a, scorer, text):
    keymap, k, apos = parse_layout(text)
    scorer.apos_key = apos if a.apostrophe != "strip" else None
    return keymap


def kpl_kw(a, value=None):
    """KPL settings from the command line; `value` overrides the swept one."""
    kw = {"wrong_cost": a.wrong_cost, "order": a.order, "divisor": a.divisor,
          "per_letter": a.per_letter, "mult": a.mult, "n_longer": a.longer}
    if value is not None:
        kw["divisor" if a.order == "sorted" else "mult"] = value
    return kw


def describe_slot2(a, value=None):
    if a.order == "sorted":
        d = a.divisor if value is None else value
        per = " per extra letter" if a.per_letter else ""
        return (f"slot 1 = best exact word, then exact words and the {a.longer} best "
                f"longer words (score / {d}{per}) sorted together")
    m = a.mult if value is None else value
    return f"slot-2 completion shown when >= {m}x the runner-up"


def cmd_kpl(a, data, scorer):
    print("KPL = keystrokes per letter (space, taps and the '/- key count as keystrokes; "
          "a word's letters are the denominator)")
    print(f"{describe_slot2(a)}; each wrong completion seen costs {a.wrong_cost}")
    print(KPL_HEADER)
    rows = []
    for text in a.layout:
        keymap = setup_layout(a, scorer, text)
        c = kpl_eval(data, scorer, keymap, True, **kpl_kw(a))
        u = kpl_eval(data, scorer, keymap, False, **kpl_kw(a))
        rows.append((text, c))
        print(kpl_row(text, c, u), flush=True)
    print("\nKPL by word length (with context)")
    print(f"{'layout':<40} " + " ".join(f"{('len ' + str(n) + ('+' if n == 8 else '')):>7}" for n in range(1, 9)))
    for text, c in rows:
        cells = []
        for n in range(1, 9):
            b = c["by_len"].get(n)
            cells.append(f"{b[0] / b[1]:7.3f}" if b else " " * 7)
        print(f"{text:<40} " + " ".join(cells))


def cmd_kpl_sweep(a, data, scorer):
    """Find the divisor D (order sorted) or threshold M (order ratio) with the
    lowest cost per letter."""
    keymap = setup_layout(a, scorer, a.layout)
    ctx = not a.no_context
    name = "D" if a.order == "sorted" else "M"
    if a.values is None:
        a.values = ([0.8, 1, 1.2, 1.5, 2, 3, 4, 6, 8, 10] if a.order == "sorted"
                    else [1, 1.5, 2, 3, 4, 6, 8, 10, 12, 16, 24, 32])
    print(f"layout {a.layout}; sweeping {name} ({describe_slot2(a, name)}); "
          f"wrong completion cost {a.wrong_cost}; {'with' if ctx else 'without'} context")
    print(f"{name:>7} {'KPL':>7} {'cost/letter':>11} {'completed':>9} {'wrong/w':>7}")
    seen = {}

    def run(m):
        m = round(m, 3)
        if m not in seen:
            st = kpl_eval(data, scorer, keymap, ctx, **kpl_kw(a, m))
            seen[m] = st
            print(f"{m:7.2f} {st['keys'] / st['letters']:7.3f} {st['cost'] / st['letters']:11.4f} "
                  f"{100 * st['completed'] / st['tokens']:8.1f}% {st['wrong'] / st['tokens']:7.2f}",
                  flush=True)
        return seen[m]["cost"] / seen[m]["letters"]

    for m in a.values:
        run(m)
    # refine on a log scale around the best grid point
    for _ in range(a.refine):
        ms = sorted(seen)
        best = min(ms, key=lambda m: seen[m]["cost"] / seen[m]["letters"])
        i = ms.index(best)
        lo = ms[i - 1] if i else best / 1.5
        hi = ms[i + 1] if i + 1 < len(ms) else best * 1.5
        run(math.sqrt(lo * best))
        run(math.sqrt(best * hi))
    best = min(seen, key=lambda m: seen[m]["cost"] / seen[m]["letters"])
    st = seen[best]
    print(f"\nbest {name} = {best:g}: cost/letter {st['cost'] / st['letters']:.4f}, "
          f"KPL {st['keys'] / st['letters']:.3f}")


def print_collisions(data, scorer, keymap, full, n=20):
    codes = scorer.codes(keymap)
    pen = {}
    for _, nxt in data.contexts:
        buckets = {}
        for w, cnt in nxt.items():
            buckets.setdefault(codes[w], []).append((cnt, w))
        for b in buckets.values():
            if len(b) < 2:
                continue
            b.sort(reverse=True)
            for i in range(len(b)):
                for j in range(i + 1, len(b)):
                    key = (b[i][1], b[j][1]) if b[i][1] < b[j][1] else (b[j][1], b[i][1])
                    pen[key] = pen.get(key, 0) + b[j][0]
    print("\nworst colliding pairs (same key sequence, both common after the same word;"
          " penalty = sum of the smaller count)")
    for (a, b), v in sorted(pen.items(), key=lambda kv: -kv[1])[:n]:
        print(f"  {data.form[a]:<12} {data.form[b]:<12} {v}")
    print("\nwrong top guesses (wanted word lost the space slot, in bigram tokens)")
    for (x, w), cnt in sorted(full["pairs"].items(), key=lambda kv: -kv[1])[:n]:
        print(f"  wanted {data.form[w]:<12} got {data.form[x]:<12} {cnt}")


def settings(a):
    return {k: v for k, v in vars(a).items() if k != "func"}


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--words", default=os.path.join(DATA_DIR, "unigrams.tsv"))
    p.add_argument("--bigrams", default=os.path.join(DATA_DIR, "bigrams.tsv"))
    p.add_argument("--lam", type=float, default=0.7, help="bigram weight in P(w|prev) (default 0.7)")
    p.add_argument("--bar", type=int, default=3, help="candidates visible in the bar (default 3)")
    p.add_argument("--cost-space", type=float, default=1.0)
    p.add_argument("--cost-bar", type=float, default=2.0, help="tap a visible candidate (default 2)")
    p.add_argument("--cost-more", type=float, default=4.0, help="expand the bar and tap (default 4)")
    p.add_argument("--penalty", choices=("min", "product"), default="min",
                   help="pair penalty for two words on one key sequence (default min)")
    p.add_argument("--objective", choices=("collision", "cost"), default="collision",
                   help="optimize collision score (default) or selection cost J")
    p.add_argument("--apostrophe", choices=("own", "on-key", "strip"), default="own",
                   help="' and - always share one key. own: that key is the function key, "
                        "so it/it's and e-mail/email never collide (default). "
                        "on-key: '/- is a 27th symbol the search places on one of the "
                        "letter keys (alphabetical variants put it after z). strip: "
                        "ignore ' and - completely. In score mode, putting ' or - inside "
                        "a group (e.g. qtbuy') places the '/- key there")
    p.add_argument("--max-per-key", type=int, default=0, help="letters allowed on one key (0 = no limit)")
    p.add_argument("--seed", type=int, default=1)
    sub = p.add_subparsers(dest="mode", required=True)

    s = sub.add_parser("pilot", help="short runs of both variants to choose one")
    s.add_argument("--keys", type=int, nargs="+", default=[7, 8])
    s.add_argument("--variants", nargs="+", choices=("free", "alpha", "hybrid", "hybrid-skip"),
                   default=["free", "alpha"])
    s.add_argument("--starts", type=int, default=3)
    s.add_argument("--moves", type=int, default=2000)
    s.add_argument("--out", default="pilot_results.json")
    s.set_defaults(func=cmd_pilot)

    s = sub.add_parser("full", help="full search for one variant")
    s.add_argument("--variant", choices=("free", "alpha", "hybrid", "hybrid-skip"), required=True,
                   help="hybrid = K-1 keys of unbroken alphabet runs + 1 key for the leftovers; "
                        "hybrid-skip = same, but runs may skip over leftover letters")
    s.add_argument("--keys", type=int, nargs=1, default=[7])
    s.add_argument("--starts", type=int, default=30)
    s.add_argument("--moves", type=int, default=20000)
    s.add_argument("--rerank", type=int, default=20, help="layouts re-scored on full J")
    s.add_argument("--polish", type=int, default=3, help="layouts hill-climbed on full J")
    s.add_argument("--screen", type=int, default=8, help="neighbours tested on J per round")
    s.add_argument("--rounds", type=int, default=30)
    s.add_argument("--out", default="layout.json")
    s.set_defaults(func=cmd_full)

    s = sub.add_parser("exhaust", help="try every alphabetical layout (exact on C0)")
    s.add_argument("--keys", type=int, nargs=1, default=[7])
    s.add_argument("--rerank", type=int, default=200, help="best layouts on C0 re-scored on C")
    s.add_argument("--out", default="layout_alpha.json")
    s.set_defaults(func=cmd_exhaust)

    def slot2_args(s):
        s.add_argument("--order", choices=("sorted", "ratio"), default="sorted",
                       help="sorted (default): slot 1 = best exact word; then the other "
                            "exact words and the LONGER best longer words (score / DIVISOR) "
                            "sorted together. ratio: slot 2 shows the best longer word only "
                            "if >= MULT x the runner-up")
        s.add_argument("--longer", type=int, default=3,
                       help="longer words added to the list in sorted order (default 3)")
        s.add_argument("--divisor", type=float, default=1.2,
                       help="score divisor for longer words in sorted order (default 1.2)")
        s.add_argument("--per-letter", action="store_true",
                       help="apply the divisor once per extra letter instead of once")
        s.add_argument("--mult", type=float, default=1.2, help="threshold for --order ratio")
        s.add_argument("--wrong-cost", type=float, default=0.1,
                       help="cost of each wrong completion the user sees (default 0.1)")

    s = sub.add_parser("kpl", help="keystrokes per letter with slot-2 prefix completion")
    s.add_argument("--layout", action="append", required=True,
                   help="repeat to compare several layouts")
    slot2_args(s)
    s.set_defaults(func=cmd_kpl)

    s = sub.add_parser("kpl-sentences", help="KPL on real sentences (Tatoeba .tsv or one per line)")
    s.add_argument("--sentences", required=True, help="e.g. data/raw/tatoeba/eng_sentences.tsv")
    s.add_argument("--layout", action="append", required=True, help="repeat to compare layouts")
    slot2_args(s)
    s.add_argument("--lang", default="eng", help="Tatoeba language column to keep (default eng)")
    s.add_argument("--every", type=int, default=1,
                   help="only sentences with id %% EVERY == OFFSET (a held-out slice)")
    s.add_argument("--offset", type=int, default=0)
    s.add_argument("--limit", type=int, default=0, help="stop after this many sentences")
    s.add_argument("--oov-cost", type=float, default=2.0,
                   help="extra keys for a word not in the word list (default 2)")
    s.add_argument("--skip-oov", action="store_true",
                   help="leave sentences with unknown words out of the per-sentence numbers")
    s.add_argument("--no-context", action="store_true", help="rank by word counts only")
    s.set_defaults(func=cmd_kpl_sentences)

    s = sub.add_parser("kpl-sweep", help="find the best slot-2 divisor D (or threshold M)")
    s.add_argument("--layout", required=True)
    s.add_argument("--values", type=float, nargs="+", default=None,
                   help="D values (sorted) or M values (ratio) to try")
    s.add_argument("--refine", type=int, default=3, help="extra refinement rounds")
    slot2_args(s)
    s.add_argument("--no-context", action="store_true", help="rank by word counts only")
    s.set_defaults(func=cmd_kpl_sweep)

    s = sub.add_parser("score", help="score one layout, e.g. \"abc def ghi ...\"")
    s.add_argument("--layout", required=True)
    s.set_defaults(func=cmd_score)

    a = p.parse_args()
    set_alphabet(a.apostrophe)
    data = Data(a.words, a.bigrams, a.lam, a.apostrophe)
    scorer = Scorer(data, a.bar, a.cost_space, a.cost_bar, a.cost_more, a.penalty, a.objective)
    a.func(a, data, scorer)


if __name__ == "__main__":
    main()
