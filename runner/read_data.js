// Data loading and lookups. Ranking lives in ranker.js.
// en_keyed.json / zh_keyed.json are written by get_sequences.py / get_chinese_sequences.py.
import EN_KEYED from "../data/curated/en_keyed.json" with { type: "json" };
import ZH_KEYED from "../data/curated/zh_keyed.json" with { type: "json" };
import { en_maps } from "./maps.js";

// Binary search: index of the first key >= p in a sorted array.
function lower_bound(keys, p) {
  let lo = 0, hi = keys.length;
  while (lo < hi) {
    const m = (lo + hi) >> 1;
    keys[m] < p ? (lo = m + 1) : (hi = m);
  }
  return lo;
}

// Narrows the previous keypress's result instead of starting over.
const filter_cache = new Map();
function filtered(tag, list, keys, codes_of) {
  if (!keys) return list;
  const id = tag + "\0" + keys;
  let r = filter_cache.get(id);
  if (r) return r;
  const base = keys.length > 1 ? filtered(tag, list, keys.slice(0, -1), codes_of) : list;
  r = base.filter(([w]) => codes_of(w).some((c) => c.startsWith(keys)));
  filter_cache.set(id, r);
  return r;
}
// Call when the previous word / committed text changes, to keep memory flat.
export function clear_filter_cache() {
  filter_cache.clear();
}

// ---------------------------------------------------------------- English

const en_exact = new Map(EN_KEYED.exact), en_keys = EN_KEYED.exact.map((p) => p[0]);
const en_next_data = EN_KEYED.next;
const en_cache = new Map(), en_next_cache = new Map(), en_code_cache = new Map();

export const en_uni = new Map(); // word -> count
export let en_uni_total = 0;
for (const [, words] of EN_KEYED.exact)
  for (const w in words) {
    en_uni.set(w, words[w]);
    en_uni_total += words[w];
  }

// Key code of a word ("Mr." -> "45", "'em" -> "24").
export function en_code(word) {
  let c = en_code_cache.get(word);
  if (c === undefined) {
    c = "";
    for (const ch of word.toLowerCase().replace(/^'/, "").replace(/\.$/, "")) c += en_maps[ch] ?? "";
    en_code_cache.set(word, c);
  }
  return c;
}

// All words whose code starts with p: [[word, count], ...] best first.
export function en_lookup(p) {
  let r = en_cache.get(p);
  if (r) return r;
  r = [];
  for (let i = lower_bound(en_keys, p); i < en_keys.length && en_keys[i].startsWith(p); i++)
    r.push(...Object.entries(en_exact.get(en_keys[i])));
  r.sort((a, b) => b[1] - a[1]);
  en_cache.set(p, r);
  return r;
}

function en_prev_key(prev) {
  return prev === "<s>" ? prev : prev.toLowerCase().replace(/\.$/, "");
}

// Words seen after prev: [[word, count], ...] best first. "<s>" = sentence start.
export function en_next(prev) {
  const key = en_prev_key(prev);
  let r = en_next_cache.get(key);
  if (!r) {
    r = Object.hasOwn(en_next_data, key) ? Object.entries(en_next_data[key]) : [];
    en_next_cache.set(key, r);
  }
  return r;
}

// en_next(prev), only words whose code starts with keys.
export function en_next_keys(prev, keys) {
  return filtered("en|" + en_prev_key(prev), en_next(prev), keys, (w) => [en_code(w)]);
}

const en_next_total = new Map();
// Sum of all counts in en_next(prev).
export function en_next_sum(prev) {
  const key = en_prev_key(prev);
  let t = en_next_total.get(key);
  if (t === undefined) {
    t = 0;
    for (const [, c] of en_next(prev)) t += c;
    en_next_total.set(key, t);
  }
  return t;
}

// ---------------------------------------------------------------- Chinese

export const zh_exact = new Map(ZH_KEYED.exact); // code -> {word: count}
const zh_keys = ZH_KEYED.exact.map((p) => p[0]);
const zh_phr = ZH_KEYED.phrases, zh_phr_keys = Object.keys(zh_phr);
const zh_cache = new Map(), zh_chr_cache = new Map();

// All words whose code starts with p: [[word, count], ...] best first.
export function zh_lookup(p) {
  let r = zh_cache.get(p);
  if (r) return r;
  const b = new Map();
  for (let i = lower_bound(zh_keys, p); i < zh_keys.length && zh_keys[i].startsWith(p); i++)
    for (const [w, c] of Object.entries(zh_exact.get(zh_keys[i]))) if (!(b.get(w) >= c)) b.set(w, c);
  r = [...b].sort((a, b) => b[1] - a[1]);
  zh_cache.set(p, r);
  return r;
}

// Rest of every phrase that starts with left: [[right, count], ...] best first.
export function zh_next(left) {
  let r = zh_chr_cache.get(left);
  if (r) return r;
  r = [];
  for (let i = lower_bound(zh_phr_keys, left); i < zh_phr_keys.length && zh_phr_keys[i].startsWith(left); i++) {
    const w = zh_phr_keys[i];
    if (w.length > left.length) r.push([w.slice(left.length), zh_phr[w]]);
  }
  r.sort((a, b) => b[1] - a[1]);
  zh_chr_cache.set(left, r);
  return r;
}

// word -> best count, phrase -> its codes. Built once, after load.
let zh_uni = null, zh_phr_codes = null;
export let zh_uni_total = 0; // counts + 1 each
export function build_zh_index() {
  if (zh_uni) return;
  zh_uni = new Map();
  zh_phr_codes = new Map();
  for (const [code, words] of ZH_KEYED.exact)
    for (const w in words) {
      const c = words[w];
      if (!(zh_uni.get(w) >= c)) zh_uni.set(w, c);
      if (w.length > 1) {
        const a = zh_phr_codes.get(w);
        a ? a.push(code) : zh_phr_codes.set(w, [code]);
      }
    }
  for (const c of zh_uni.values()) zh_uni_total += c + 1;
}
setTimeout(build_zh_index, 0); // so the first keypress doesn't wait

export function zh_count(word) {
  build_zh_index();
  return zh_uni.get(word) ?? 0;
}

// Codes of `right` as typed after `left` (one per reading).
// Every syllable code ends in a tone letter a-e.
export function zh_right_codes(left, right) {
  build_zh_index();
  const n = [...left].length;
  return zh_phr_codes.get(left + right).map((c) => c.match(/\d+[a-e]/g).slice(n).join(""));
}

// zh_next(left), only continuations whose code starts with keys.
export function zh_next_keys(left, keys) {
  return filtered("zh|" + left, zh_next(left), keys, (right) => zh_right_codes(left, right));
}

const zh_next_total = new Map();
// Sum of all counts (+1 each) in zh_next(left).
export function zh_next_sum(left) {
  let t = zh_next_total.get(left);
  if (t === undefined) {
    t = 0;
    for (const [, c] of zh_next(left)) t += c + 1;
    zh_next_total.set(left, t);
  }
  return t;
}
