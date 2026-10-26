// Candidate ranking. Data and lookups live in read_data.js.
// score = lam * P(word | context) + (1 - lam) * P(word); context = previous
// word (English) or the end of the committed text (Chinese). Defaults N = 8,
// lam = 0.7 come from tune_en_rank.py (English only so far).
//
// Returned list: slot 1 = best word with exactly the typed code, then the other
// exact words and the 3 best longer words (score / N), sorted together.
import {
  en_code, en_lookup, en_next, en_next_keys, en_next_sum, en_uni, en_uni_total,
  build_zh_index, zh_exact, zh_lookup, zh_next, zh_next_keys, zh_next_sum, zh_right_codes, zh_count, zh_uni_total,
} from "./read_data.js";

const N_LONGER = 3; // longer words shown (tune_en_rank.py: gains stop after 3)

function order(exact_list, prefix_list) {
  exact_list.sort((a, b) => b[1] - a[1]);
  prefix_list.sort((a, b) => b[1] - a[1]);
  const options = exact_list.length ? [exact_list[0][0]] : [];
  const rest = [...exact_list.slice(1), ...prefix_list.slice(0, N_LONGER)].sort((a, b) => b[1] - a[1]);
  for (const [w] of rest) options.push(w);
  return options;
}

// prev: previous word ("" or "<s>" at the start of a sentence); seq: keys typed.
export function en_rank(prev, seq, N = 8, lam = 0.7) {
  if (prev == "") prev = "<s>";
  const values = seq == "" ? [] : en_lookup(seq);
  const next = seq == "" ? en_next(prev) : en_next_keys(prev, seq);
  const nt = en_next_sum(prev);
  const l = nt ? lam : 0; // no bigram data for prev -> word counts only

  const val_map = new Map();
  for (const [k, v] of values) val_map.set(k, ((1 - l) * v) / en_uni_total);
  for (const [k, v] of next) {
    const base = val_map.get(k) ?? ((1 - l) * (en_uni.get(k) ?? 0)) / en_uni_total;
    val_map.set(k, base + (l * v) / nt);
  }

  const exact_list = [], prefix_list = [];
  for (const [k, v] of val_map) {
    if (en_code(k) == seq) exact_list.push([k, v]);
    else prefix_list.push([k, v / N]);
  }
  return order(exact_list, prefix_list);
}

// Longest ending of the committed text (up to max chars) that starts a known phrase.
export function zh_context(text, max = 4) {
  const chars = [...text];
  for (let n = Math.min(max, chars.length); n > 0; n--) {
    const left = chars.slice(-n).join("");
    if (zh_next(left).length) return left;
  }
  return "";
}

// text: committed text so far; seq: keys typed. Counts get +1 so count-0
// dictionary words (many idioms) can still rank.
export function zh_rank(text, seq, N = 8, lam = 0.7) {
  build_zh_index();
  const left = zh_context(text);
  const nt = left ? zh_next_sum(left) : 0;
  const l = nt ? lam : 0;
  const exact = seq ? zh_exact.get(seq) ?? {} : {};
  const next = left ? (seq ? zh_next_keys(left, seq) : zh_next(left)) : [];
  const next_set = new Set(next.map(([w]) => w));

  const uni_score = (w) => ((1 - l) * (zh_count(w) + 1)) / zh_uni_total;
  const val_map = new Map();
  for (const w in exact) val_map.set(w, uni_score(w));
  if (seq) { // best longer words by count; context words are added below
    let taken = 0;
    for (const [w] of zh_lookup(seq)) {
      if (taken >= N_LONGER) break;
      if (w in exact || next_set.has(w)) continue;
      val_map.set(w, uni_score(w));
      taken++;
    }
  }
  for (const [w, c] of next) val_map.set(w, (val_map.get(w) ?? uni_score(w)) + (l * (c + 1)) / nt);

  const exact_list = [], prefix_list = [];
  for (const [w, v] of val_map) {
    const is_exact = seq && (w in exact || (next_set.has(w) && zh_right_codes(left, w).includes(seq)));
    if (is_exact) exact_list.push([w, v]);
    else prefix_list.push([w, v / N]);
  }
  return order(exact_list, prefix_list);
}

function timed(label, fn) {
  const t0 = performance.now();
  fn();
  console.log(`${label}: ${(performance.now() - t0).toFixed(1)} ms`);
}


document.addEventListener("DOMContentLoaded", async () => {
  timed("test_lookup", () => {
    console.log(en_rank("you", "1"));
    console.log(en_rank("", "16"));
    console.log(en_rank("hello", ""));
  });
});
