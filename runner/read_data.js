import EN_WORDS from "../data/curated/words.json" with { type: "json" };
import EN_NGRAMS from "../data/curated/bigrams.json" with { type: "json" };
import ZH_WORDS from "../data/curated/zh_words.json" with { type: "json" };
import ZH_NGRAMS from "../data/curated/zh_ngrams.json" with { type: "json" };
import {
  en_maps,
  zh_consonant_maps,
  zh_tone_maps,
  zh_vowel_maps,
} from "./maps.js";

export let en_prefix = {},
  en_ngram,
  zh_seqs = {},
  zh_ngram_seq,
  zh_ngram_chr,
  zh_exact = new Map(),
  zh_keys = [];
const zh_cache = new Map();
const titles = ["mr", "mrs", "ms", "dr", "st", "jr", "sr", "vs"];

function get_zh_key(str) {
  let arr = str.split(" ");
  let result = "";
  for (const bpmf of arr) {
    let consonant = bpmf.at(0),
      tone = bpmf.at(-1);
    let vowel = bpmf;
    if (consonant in zh_consonant_maps) {
      vowel = vowel.slice(1);
    } else consonant = "";
    if (tone in zh_tone_maps) {
      vowel = vowel.slice(0, -1);
    } else tone = "";
    result +=
      zh_consonant_maps[consonant] + zh_vowel_maps[vowel] + zh_tone_maps[tone];
  }
  return result;
}

function add(kei, v) {
  const bucket = (zh_seqs[kei] ??= {});
  for (const [w, c] of Object.entries(v))
    if (!(w in bucket) || bucket[w] < c) bucket[w] = c;
}
function addExact(key, v) {
  let b = zh_exact.get(key);
  if (!b) zh_exact.set(key, (b = new Map()));
  for (const w in v) if (!(b.get(w) >= v[w])) b.set(w, v[w]);
}
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
    for (const [w, c] of zh_exact.get(zh_keys[i]))
      if (!(b.get(w) >= c)) b.set(w, c);
  r = [...b].sort((a, b) => b[1] - a[1]);
  zh_cache.set(p, r);
  return r;
}

function timed(label, fn) {
  const t0 = performance.now();
  fn();
  console.log(`${label}: ${(performance.now() - t0).toFixed(1)} ms`);
}
document.addEventListener("DOMContentLoaded", async () => {
  en_ngram = EN_NGRAMS;
  const start = performance.now();
  timed("en_prefix", () => {
    for (const [k, v] of Object.entries(EN_WORDS)) {
      const lower = k.toLowerCase().replace(/^'/, ""),
        word = titles.includes(lower) ? k + "." : k;
      let keymap = "";
      for (const letter of lower) {
        keymap += en_maps[letter];
        en_prefix[keymap] ??= {};
        en_prefix[keymap][word] = v;
      }
    }
  });
  timed("zh_words", () => {
    for (const k in ZH_WORDS) addExact(get_zh_key(k), ZH_WORDS[k]);
  });
  timed("zh_ngrams", () => {
    for (const k in ZH_WORDS) addExact(get_zh_key(k), ZH_WORDS[k]);
    for (const k in ZH_NGRAMS)
      for (const k2 in ZH_NGRAMS[k])
        addExact(get_zh_key(k + " " + k2), ZH_NGRAMS[k][k2]);
  });
  console.log(
    `total: ${(performance.now() - start).toFixed(1)} ms,`,
    Object.keys(en_prefix).length,
    "en prefixes,",
    zh_exact.size,
    "zh prefixes",
  );
  console.log(zh_exact);
});
