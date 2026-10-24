import EN_KEYED from "../data/curated/en_keyed.json" with { type: "json" };
import ZH_KEYED from "../data/curated/zh_keyed.json" with { type: "json" };

const en_exact = new Map(EN_KEYED.exact),
  en_keys = EN_KEYED.exact.map((p) => p[0]),
  en_cache = new Map();
const en_next_data = EN_KEYED.next,
  en_next_cache = new Map();
const zh_exact = new Map(ZH_KEYED.exact),
  zh_keys = ZH_KEYED.exact.map((p) => p[0]),
  zh_cache = new Map();
const zh_phr = ZH_KEYED.phrases,
  zh_phr_keys = Object.keys(zh_phr),
  zh_chr_cache = new Map();

export function zh_lookup(p) {
  let r = zh_cache.get(p);
  if (r) return r;
  let lo = 0,
    hi = zh_keys.length;
  while (lo < hi) {
    const m = (lo + hi) >> 1;
    zh_keys[m] < p ? (lo = m + 1) : (hi = m);
  }
  const b = new Map();
  for (let i = lo; i < zh_keys.length && zh_keys[i].startsWith(p); i++)
    for (const [w, c] of Object.entries(zh_exact.get(zh_keys[i])))
      if (!(b.get(w) >= c)) b.set(w, c);
  r = [...b].sort((a, b) => b[1] - a[1]);
  zh_cache.set(p, r);
  return r;
}

// [[word, count], ...] best first; pass "<s>" at the start of a sentence
export function en_next(prev) {
  const key = prev === "<s>" ? prev : prev.toLowerCase().replace(/\.$/, "");
  let r = en_next_cache.get(key);
  if (!r) {
    r = Object.hasOwn(en_next_data, key)
      ? Object.entries(en_next_data[key])
      : [];
    en_next_cache.set(key, r);
  }
  return r;
}
export function en_lookup(p) {
  let r = en_cache.get(p);
  if (r) return r;
  let lo = 0,
    hi = en_keys.length;
  while (lo < hi) {
    const m = (lo + hi) >> 1;
    en_keys[m] < p ? (lo = m + 1) : (hi = m);
  }
  r = [];
  for (let i = lo; i < en_keys.length && en_keys[i].startsWith(p); i++)
    r.push(...Object.entries(en_exact.get(en_keys[i])));
  r.sort((a, b) => b[1] - a[1]);
  en_cache.set(p, r);
  return r;
}

export function zh_next(left) {
  let r = zh_chr_cache.get(left);
  if (r) return r;
  let lo = 0,
    hi = zh_phr_keys.length;
  while (lo < hi) {
    const m = (lo + hi) >> 1;
    zh_phr_keys[m] < left ? (lo = m + 1) : (hi = m);
  }
  r = [];
  for (
    let i = lo;
    i < zh_phr_keys.length && zh_phr_keys[i].startsWith(left);
    i++
  ) {
    const w = zh_phr_keys[i];
    if (w.length > left.length) r.push([w.slice(left.length), zh_phr[w]]);
  }
  r.sort((a, b) => b[1] - a[1]);
  zh_chr_cache.set(left, r);
  return r;
}

function timed(label, fn) {
  const t0 = performance.now();
  fn();
  console.log(`${label}: ${(performance.now() - t0).toFixed(1)} ms`);
}

document.addEventListener("DOMContentLoaded", async () => {
  timed("test_lookup", () => {
    zh_lookup("6");
    en_lookup("1");
    zh_next("巴");
    console.log(en_next("Mr."));
  });
});
