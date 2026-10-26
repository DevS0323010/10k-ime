import {
  en_layouts, zh_layouts, zh_groups, zh_vowels, zh_vowel_by_code, zh_vowel_fallback, zh_tones,
  zh_quote_cycles, ZH_NO_INITIAL, EN_NO_CAPITAL_AFTER, EN_TITLES, SYM,
} from "./maps.js";
import { en_rank, zh_rank } from "./ranker.js";
import { clear_filter_cache } from "./read_data.js";

const SLOTS = 5; // candidate buttons "00".."04"
const ALL_SLOTS = 15; // expanded list: candidates on all 3 rows
const MULTITAP_MS = 1000; // same key again within this time = next character

const st = {
  lang: "en", // "en" | "zh"
  mode: "main", // "main" | "fn" | "punc" | "number" | "ts" | "ts_consonant" | "ts_vowel"
  text: "", // committed text before the cursor
  after: "", // committed text after the cursor
  en_buf: "", // English: key digits of the word being typed
  zh_done: [], // Chinese: finished syllables of the word being typed
  zh_cur: {}, // Chinese: syllable being typed {group, initial, ini_label, vowel, coda, tone}
  cands: [],
  page: 0,
  expanded: false, // "…" opened: candidates cover the keys
  xpage: 0, // page of the expanded list
  caps: 0, // 0 lower, 1 Title (next word only), 2 SCREAMING (stays)
  tap: null, // last multi-tap {id, time, base, variants, i}
};

const $ = (id) => document.getElementById(id);
const K = (label, act, val, off = false) => ({ label, act, val, off });
const chars = (s) => [...s];

// ------------------------------------------------------------ text helpers

function delete_last_char() {
  st.text = chars(st.text).slice(0, -1).join("");
  clear_filter_cache();
}

// Backspace with nothing being typed: an English word before the cursor
// (with the space after it) goes as a whole; anything else, like a Chinese
// character or punctuation, goes one character at a time. This depends on
// the text, not the current language, so mixed text works either way.
const EN_WORD_END = /[A-Za-z][A-Za-z'\-]*\.? ?$/;
function delete_back() {
  const m = st.text.match(EN_WORD_END);
  if (m && (m.index === 0 || !/[A-Za-z0-9]/.test(st.text[m.index - 1]))) {
    st.text = st.text.slice(0, m.index);
    clear_filter_cache();
  } else delete_last_char();
}

function last_token() {
  const m = st.text.match(/(\S+)\s*$/);
  return m ? m[1] : "";
}

// Start of text, after a newline, or after . ! ? … (except "Mr." and the like).
function at_sentence_start() {
  const t = st.text.replace(/[ \t]+$/, "");
  if (t === "" || t.endsWith("\n")) return true;
  const last = last_token();
  if (/[!?…。！？]$/.test(last)) return true;
  return last.endsWith(".") && !EN_TITLES.has(last.slice(0, -1).toLowerCase());
}

// Capitalize the next English word? Sentence start, and after Mr./Mrs./Ms./Dr.
function en_title_next() {
  if (at_sentence_start()) return true;
  const last = last_token();
  return last.endsWith(".") && !EN_NO_CAPITAL_AFTER.has(last.slice(0, -1).toLowerCase());
}

function en_case(word) {
  if (st.caps === 2) return word.toUpperCase();
  if (st.caps === 1 || en_title_next()) return word.charAt(0).toUpperCase() + word.slice(1);
  return word;
}

// Previous word for en_rank: "<s>" at a sentence start, else the last word
// without punctuation around it ("Mr." keeps its period).
function en_prev() {
  if (at_sentence_start()) return "<s>";
  const last = last_token();
  if (last.endsWith(".") && EN_TITLES.has(last.slice(0, -1).toLowerCase())) return last;
  return last.replace(/^[^A-Za-z']+/, "").replace(/[^A-Za-z'\-]+$/, "");
}

// ------------------------------------------------------------ Chinese syllables

function zh_stage(c) {
  if (!c.group && !c.initial) return "consonant";
  if (!c.initial) return "member";
  if (!c.vowel) return "vowel";
  if (!c.coda && zh_vowel_by_code[c.vowel].codas) return "coda";
  return "tone"; // after a coda, or after ㄭ/ㄦ
}

// Alternative codes of one (possibly unfinished) syllable.
function zh_syllable_codes(c) {
  const head = c.initial ?? c.group ?? "";
  if (!c.vowel) return [head];
  let rests = [c.vowel];
  if (c.coda) {
    rests = [zh_vowel_fallback[c.vowel][c.coda]];
    if (c.initial === ZH_NO_INITIAL && c.vowel === "2" && c.coda === "1") rests = ["61", "21"]; // ㄧ or ㄧㄞ (崖)
  }
  return rests.map((r) => head + r + (c.tone ?? ""));
}

function zh_composing() {
  return st.zh_done.length > 0 || Object.keys(st.zh_cur).length > 0;
}

// Every code the typed syllables can stand for.
function zh_seqs() {
  let seqs = [""];
  for (const c of [...st.zh_done, st.zh_cur]) {
    const alts = zh_syllable_codes(c);
    seqs = seqs.flatMap((s) => alts.map((a) => s + a));
  }
  return seqs.filter((s) => s);
}

function zh_syllable_label(c) {
  let s = c.ini_label ?? (c.group ? zh_groups[c.group - 1].label + "?" : "");
  if (s === "Ø") s = "";
  if (c.vowel) {
    const v = zh_vowel_by_code[c.vowel];
    s += c.coda ? v.codas[c.coda - 1] : v.label;
  }
  if (c.tone) s += zh_tones.find(([, t]) => t === c.tone)[0];
  return s;
}

function zh_back() {
  const c = st.zh_cur;
  if (c.coda) delete c.coda;
  else if (c.vowel) delete c.vowel;
  else if (c.initial) { delete c.initial; delete c.ini_label; }
  else if (c.group) delete c.group;
  else if (st.zh_done.length) {
    st.zh_cur = st.zh_done.pop();
    delete st.zh_cur.tone;
  }
}

// ------------------------------------------------------------ layouts

function main_layout() {
  if (st.lang === "en") {
    const l = en_layouts.main.map((row) => [...row]);
    if (st.en_buf) l[0][0] = K("'-", "key", "-"); // inside a word, Fn types ' or -
    return l;
  }
  const c = st.zh_cur, stage = zh_stage(c), BS = K(SYM.bs, "bs");
  const groups = zh_groups.map((g) => K(g.label, "zh_group", g.code));
  const tones = zh_tones.map(([label, t]) => K(label, "zh_tone", t));
  switch (stage) {
    case "consonant":
      return [[K(SYM.fn, "fn"), K(SYM.space, "space"), K(SYM.punc, "punc"), K("Ø", "zh_initial", [ZH_NO_INITIAL, "Ø"]), BS], groups];
    case "member": {
      const g = zh_groups[c.group - 1];
      groups[c.group - 1] = { ...groups[c.group - 1], on: true };
      return [[...g.members.map(([label, code]) => K(label, "zh_initial", [code, label])), BS], groups];
    }
    case "vowel":
      return [
        [...zh_vowels[0].map((v) => K(v.label, "zh_vowel", v.code)), BS],
        zh_vowels[1].map((v) => K(v.label, "zh_vowel", v.code)),
      ];
    default: { // coda or tone
      const v = zh_vowel_by_code[c.vowel];
      const codas = [0, 1, 2, 3].map((i) =>
        v.codas ? K(v.codas[i], "zh_coda", String(i + 1), stage === "tone") : K("", "none", null, true));
      return [[...codas, BS], tones];
    }
  }
}

// English letter labels show the Caps state: abcd, Abcd (next word), ABCD (locked).
function caps_label(label) {
  if (st.caps === 2) return label.toUpperCase();
  if (st.caps === 1) return label.charAt(0).toUpperCase() + label.slice(1).toLowerCase();
  return label.toLowerCase();
}

function with_caps(lay) {
  if (st.lang !== "en") return lay;
  return lay.map((row) => row.map((key) => {
    if (key.act === "key" && key.val !== "-" || key.act === "letter" || key.act === "mode" && key.val === "ts")
      return { ...key, label: caps_label(key.label) };
    if (key.act === "caps") return { ...key, label: st.caps === 2 ? SYM.caps_lock : SYM.caps, on: st.caps > 0 };
    return key;
  }));
}

function layout() {
  if (st.mode === "main") return with_caps(main_layout());
  return with_caps((st.lang === "en" ? en_layouts : zh_layouts)[st.mode]);
}

// ------------------------------------------------------------ candidates

function refresh_cands() {
  st.page = 0;
  st.expanded = false;
  if (st.mode !== "main") return (st.cands = []);
  if (st.lang === "en") st.cands = en_rank(en_prev(), st.en_buf);
  else st.cands = zh_rank(st.text, zh_composing() ? zh_seqs() : "");
}

function shown(word) {
  return st.lang === "en" ? en_case(word) : word;
}

function per_page() {
  return st.cands.length > SLOTS ? SLOTS - 1 : SLOTS;
}

function commit(word) {
  if (st.lang === "en") {
    st.text += en_case(word) + (st.after.startsWith(" ") ? "" : " ");
    if (st.caps === 1) st.caps = 0; // Title is one-shot
    st.en_buf = "";
  } else {
    st.text += word;
    st.zh_done = [];
    st.zh_cur = {};
  }
  clear_filter_cache();
}

// Commit the top candidate if a word is being typed (before fn / punctuation).
function commit_pending() {
  const typing = st.lang === "en" ? st.en_buf : zh_composing();
  if (typing && st.cands.length) commit(st.cands[0]);
  st.en_buf = "";
  st.zh_done = [];
  st.zh_cur = {};
}

function on_candidate(col) {
  if (st.cands.length > SLOTS && col === SLOTS - 1) { // "…": open the full list over the keys
    st.expanded = true;
    st.xpage = 0;
    return;
  }
  const i = st.page * per_page() + col;
  if (i < st.cands.length) {
    commit(st.cands[i]);
    refresh_cands();
  }
}

// Expanded list: slot 4 (top right) closes it; if more candidates remain than
// fit, slot 14 (bottom right) shows the next page. Returns [label, action]
// for each of the 15 slots, row by row.
function expanded_slots() {
  const free = ALL_SLOTS - 1;
  const more = st.cands.length > free;
  const per = more ? free - 1 : free;
  const start = st.xpage * per;
  const out = [];
  let i = start;
  for (let s = 0; s < ALL_SLOTS; s++) {
    if (s === 4) out.push(["▲", "close"]);
    else if (more && s === ALL_SLOTS - 1) out.push(["▼", "more"]);
    else if (i < st.cands.length) out.push([shown(st.cands[i]), i++]);
    else out.push(["", null]);
  }
  return { out, per, more };
}

function on_expanded(slot) {
  const { out, per } = expanded_slots();
  const [, act] = out[slot];
  if (act === "close") st.expanded = false;
  else if (act === "more") st.xpage = (st.xpage + 1) * per < st.cands.length ? st.xpage + 1 : 0;
  else if (typeof act === "number") {
    commit(st.cands[act]);
    refresh_cands();
  }
}

// ------------------------------------------------------------ inserting text

// Multi-tap: the same key again within MULTITAP_MS replaces what it inserted.
function multitap(id, variants, insert) {
  const now = Date.now(), t = st.tap;
  if (t && t.id === id && now - t.time < MULTITAP_MS) {
    t.i = (t.i + 1) % t.variants.length;
    t.time = now;
    st.text = t.base;
    insert(t.variants[t.i]);
    return;
  }
  st.tap = { id, time: now, base: st.text, variants, i: 0 };
  insert(variants[0]);
}

const EN_CLOSING = /^[,.…:;!?)>]/;
const EN_SPACE_AFTER = new Set([",", ".", "…", ":", ";", "!", "?"]);

function insert_punct(p) {
  if (st.lang === "en") {
    if (EN_CLOSING.test(p) && st.text.endsWith(" ")) st.text = st.text.slice(0, -1); // "word ," -> "word,"
    st.text += p + (EN_SPACE_AFTER.has(p) ? " " : "");
  } else st.text += p;
  clear_filter_cache();
}

function insert_raw(s) {
  st.text += s;
  clear_filter_cache();
}

// Title (caps 1) makes the next letter a capital, then turns itself off
// with the letter after it. Multi-tap on that same letter stays a capital.
let title_at = null;
function insert_letter(s) {
  if (st.caps === 1 && title_at !== null && title_at !== st.text.length) {
    st.caps = 0;
    title_at = null;
  }
  if (st.caps === 2) s = s.toUpperCase();
  else if (st.caps === 1) {
    s = s.toUpperCase();
    title_at = st.text.length;
  } else if (/(^|\s)$/.test(st.text) && en_title_next()) s = s.toUpperCase();
  st.text += s;
}

// Bracket key: if one is open, the close one comes first.
function pair_variants([open, close], base) {
  const depth = chars(base).reduce((d, ch) => d + (ch === open) - (ch === close), 0);
  return depth > 0 ? [close, open] : [open, close];
}

function quote_variants(base) {
  let open = "none";
  const stack = [];
  for (const ch of base) {
    if (ch === "「" || ch === "『") stack.push(ch);
    else if ((ch === "」" || ch === "』") && stack.length) stack.pop();
  }
  if (stack.length) open = stack.at(-1);
  return zh_quote_cycles[open];
}

// ------------------------------------------------------------ keys

function speak() {
  if (!("speechSynthesis" in globalThis)) return;
  const u = new SpeechSynthesisUtterance(st.text + st.after);
  u.lang = st.lang === "zh" ? "zh-TW" : "en-US";
  speechSynthesis.speak(u);
}

function on_key(id, key) {
  if (key.off) return;
  if (!["tap", "raw", "letter", "pair", "quote"].includes(key.act)) st.tap = null;
  const c = st.zh_cur;
  switch (key.act) {
    // ---- English main
    case "key":
      st.en_buf += key.val;
      break;
    // ---- shared main
    case "space":
      if (st.mode === "main" && st.lang === "en" && st.en_buf) {
        if (st.cands.length) commit(st.cands[0]); // keys that match no word stay for backspace
      } else if (st.mode === "main" && st.lang === "zh" && zh_composing()) {
        if (st.cands.length) commit(st.cands[0]);
      } else insert_raw(" ");
      break;
    case "bs":
      st.tap = null;
      if (st.mode === "main" && st.lang === "en" && st.en_buf) st.en_buf = st.en_buf.slice(0, -1);
      else if (st.mode === "main" && st.lang === "zh" && zh_composing()) zh_back();
      else delete_back();
      break;
    case "fn":
      commit_pending();
      st.mode = "fn";
      break;
    case "punc": // Chinese main row: straight to punctuation
      commit_pending();
      st.mode = "punc";
      break;
    // ---- Chinese main
    case "zh_group":
      c.group = key.val; // pressing another group switches without backspace
      delete c.initial;
      delete c.ini_label;
      break;
    case "zh_initial":
      [c.initial, c.ini_label] = key.val;
      break;
    case "zh_vowel":
      c.vowel = key.val;
      break;
    case "zh_coda":
      c.coda = key.val;
      break;
    case "zh_tone":
      c.tone = key.val;
      st.zh_done.push(c);
      st.zh_cur = {};
      break;
    // ---- fn menu
    case "exit":
      st.mode = "main";
      break;
    case "mode":
      st.mode = key.val;
      break;
    case "newline":
      insert_raw("\n");
      st.mode = "main";
      break;
    case "lang":
      st.lang = st.lang === "en" ? "zh" : "en";
      st.mode = "main";
      break;
    case "clear":
      st.text = "";
      st.after = "";
      clear_filter_cache();
      st.mode = "main";
      break;
    case "copy":
      navigator.clipboard?.writeText(st.text + st.after);
      st.mode = "main";
      break;
    case "tts":
      speak();
      st.mode = "main";
      break;
    case "caps": // stays in the menu so it can be pressed again
      st.caps = (st.caps + 1) % 3;
      title_at = null;
      break;
    // ---- multi-tap modes ("classic")
    case "tap":
      multitap(id, key.val, insert_punct);
      break;
    case "raw":
      multitap(id, key.val, insert_raw);
      break;
    case "letter":
      multitap(id, key.val, insert_letter);
      break;
    case "pair":
      multitap(id, st.tap?.id === id ? st.tap.variants : pair_variants(key.val, st.text), insert_punct);
      break;
    case "quote":
      multitap(id, st.tap?.id === id ? st.tap.variants : quote_variants(st.text), insert_punct);
      break;
  }
  if (key.act !== "none") refresh_cands();
}

// ------------------------------------------------------------ drawing

// Key color groups (style.css colors buttons by data-kind).
const KIND = {
  key: "input", letter: "input", raw: "input", zh_initial: "input",
  zh_group: "group", zh_vowel: "vowel", zh_coda: "coda", zh_tone: "tone",
  tap: "punc", pair: "punc", quote: "punc", punc: "control",
  space: "space", bs: "delete", clear: "delete",
  fn: "control", exit: "control", mode: "control", lang: "control", caps: "control",
  newline: "control", copy: "control", tts: "control", none: "none",
};

// Label sizes. All keys share one size (and the candidates another), so "T"
// is not huge next to "LMN": the size that fits the middle label. Labels
// longer than that shrink on their own instead of shrinking every key.
const measure = document.createElement?.("canvas")?.getContext?.("2d");
// Largest label: a share of the button height and of its width, so a
// one-glyph key ("Fn", "ㄅ") isn't far bigger than a word ("Space").
const KEY_MAX = [0.4, 0.46], CAND_MAX = [0.46, 0.62], ROOM_W = 0.86;
// Zhuyin and tone marks are drawn small inside their em box; scale them up
// so they look as big as the Latin and Han labels next to them.
// Full-width punctuation (，。「」) is small for the same reason.
const ZHUYIN = /^[\u3100-\u312f\u31a0-\u31bf/\s]+$/u, TONES = /^[ˇˋˊ˙ˉ]+$/u;
const CJK_PUNCT = /^[\u3000-\u303f\uff00-\uff65…—\s]+$/u;
// Some key symbols are small glyphs too.
const SYMBOL_SCALE = { [SYM.space]: 1.8, [SYM.tts]: 1.3, [SYM.copy]: 1.15, [SYM.newline]: 1.15 };
const glyph_scale = (t) =>
  SYMBOL_SCALE[t] ?? (TONES.test(t) ? 2.4 : ZHUYIN.test(t) || CJK_PUNCT.test(t) ? 1.3 : 1);

// h: the height to size against (the shortest button of the group, so a
// shorter row doesn't end up with smaller labels than the rows below it).
function fit_size(el, [h_share, w_share], h = el.clientHeight) {
  const text = el.innerText;
  if (!measure || !text || !el.clientWidth) return [Infinity, Infinity];
  const cs = getComputedStyle(el);
  measure.font = `${cs.fontWeight} 100px ${cs.fontFamily}`;
  const lines = text.split("\n");
  const w = Math.max(...lines.map((l) => measure.measureText(l).width)) / 100; // width per 1px of font size
  const fits = (el.clientWidth * ROOM_W) / Math.max(w, 0.01); // widest size that fits
  const high = (h * 0.8) / (lines.length * 1.15); // two lines must fit too
  return [Math.min(h * h_share, el.clientWidth * w_share, fits, high), Math.min(fits, high)];
}

// A long Zhuyin label ("ㄚㄞㄠㄢㄤ") on one line gets tiny; put it on two.
function maybe_wrap(el, max) {
  const g = chars(el.innerText);
  if (g.length < 4 || /[\sA-Za-z0-9]/.test(el.innerText) || TONES.test(el.innerText)) return;
  const half = Math.ceil(g.length / 2);
  const [, one] = fit_size(el, max);
  const keep = el.innerText;
  el.innerText = g.slice(0, half).join("") + "\n" + g.slice(half).join("");
  const [, two] = fit_size(el, max);
  if (two < one * 1.2) el.innerText = keep;
}

function fit_group(els, max, wrap = false) {
  if (wrap) els.forEach((el) => maybe_wrap(el, max));
  const h = Math.min(...els.map((el) => el.clientHeight));
  const sizes = els.map((el) => fit_size(el, max, h));
  const finite = sizes.map(([cap]) => cap).filter(Number.isFinite).sort((x, y) => x - y);
  if (!finite.length) return;
  const shared = finite[Math.floor((finite.length - 1) / 2)];
  els.forEach((el, i) => {
    const multi = el.innerText.includes("\n");
    const k = Math.min(glyph_scale(el.innerText), multi ? 1.3 : Infinity), [cap, fits] = sizes[i];
    const size = Math.min(shared, cap) * k <= fits ? Math.min(shared, cap) * k : fits;
    el.style.fontSize = Math.max(11, size) + "px";
  });
}

function fit_all() {
  const row = (r) => [0, 1, 2, 3, 4].map((c) => $("" + r + c));
  if (st.expanded) fit_group([...row(0), ...row(1), ...row(2)], CAND_MAX);
  else {
    fit_group(row(0), CAND_MAX);
    fit_group([...row(1), ...row(2)], KEY_MAX, true);
  }
}

function draw_buttons() {
  if (st.expanded) {
    const { out } = expanded_slots();
    out.forEach(([label, act], s) => {
      const el = $("" + Math.floor(s / 5) + (s % 5));
      el.innerText = label;
      el.disabled = false;
      el.classList.remove("off", "on");
      el.classList.toggle("first", s === 0 && st.xpage === 0);
      el.dataset.kind = typeof act === "number" ? "cand" : act === null ? "empty" : "control";
    });
    return fit_all();
  }
  const lay = layout();
  for (let i = 0; i < 2; i++)
    for (let j = 0; j < 5; j++) {
      const el = $("" + (i + 1) + j), key = lay[i][j];
      el.innerText = key.label;
      el.disabled = !!key.off;
      el.classList.toggle("off", !!key.off);
      el.classList.toggle("on", !!key.on);
      el.dataset.kind = KIND[key.act] ?? "input";
    }

  const per = per_page(), start = st.page * per;
  for (let i = 0; i < SLOTS; i++) {
    const el = $("0" + i);
    el.dataset.kind = "cand";
    if (st.cands.length > SLOTS && i === SLOTS - 1) {
      el.innerText = "…";
      el.dataset.kind = "more";
    } else el.innerText = start + i < st.cands.length ? shown(st.cands[start + i]) : "";
    if (el.innerText === "") el.dataset.kind = "empty";
    el.classList.toggle("first", i === 0 && el.innerText !== "");
  }
  fit_all();
}

// ------------------------------------------------------------ text box and cursor

// The textarea takes taps (to move the cursor) but its own text and caret are
// hidden; a copy laid out the same way is drawn under it. That copy shows the
// word being typed underlined and a cursor that does not blink.
const box = $("buffer");
const is_textarea = box?.tagName === "TEXTAREA" || box?.tagName === "INPUT";
let view = null, mark = null;
if (is_textarea) {
  box.readOnly = false; // Chrome hides the caret in a readonly box; beforeinput below blocks typing instead
  box.setAttribute("inputmode", "none"); // no phone keyboard: this IME is the keyboard
  box.addEventListener("beforeinput", (e) => e.preventDefault()); // no typing into it directly
  box.classList.add("buffer-input");
  view = document.createElement("div");
  view.className = "buffer-view";
  view.setAttribute("aria-hidden", "true");
  box.before(view);
  box.addEventListener("scroll", () => (view.scrollTop = box.scrollTop));
  mark = document.createElement("div");
  mark.className = "status-mark";
  box.after(mark);
}

function pending_text() {
  if (st.lang === "en" && st.en_buf) return st.cands[0] ? en_case(st.cands[0]) : st.en_buf;
  if (st.lang === "zh" && zh_composing())
    return [...st.zh_done, st.zh_cur].map(zh_syllable_label).filter((s) => s).join(" ") || "…";
  return "";
}

function span(cls, text) {
  const el = document.createElement("span");
  el.className = cls;
  el.textContent = text;
  return el;
}

function draw_text() {
  const pending = pending_text();
  const caret = st.text.length + pending.length;
  if (!is_textarea) {
    box.innerText = st.text + pending + "|" + st.after; // a plain element can't show a caret
    return;
  }
  box.value = st.text + pending + st.after;
  box.setSelectionRange(caret, caret);
  // A trailing newline needs something after it, or the last empty line has no height.
  view.replaceChildren(st.text, span("pending", pending), span("caret", ""), st.after + "\u200b");
  const c = view.querySelector(".caret"), line = c.offsetHeight;
  if (c.offsetTop < box.scrollTop) box.scrollTop = c.offsetTop;
  else if (c.offsetTop + line > box.scrollTop + box.clientHeight) box.scrollTop = c.offsetTop + line - box.clientHeight;
  view.scrollTop = box.scrollTop;
  const caps = ["", "Aa", "AA"][st.caps];
  mark.textContent = (st.lang === "en" ? "EN" : "中") + (st.lang === "en" && caps ? " · " + caps : "");
}

// The user tapped somewhere in the text (or used arrow keys): move the cursor there.
function cursor_moved() {
  if (!is_textarea) return;
  const p = box.selectionStart;
  if (st.en_buf || zh_composing()) return draw_text(); // keep the cursor while a word is being typed
  if (p === st.text.length || box.selectionStart !== box.selectionEnd) return;
  const full = st.text + st.after;
  st.text = full.slice(0, p);
  st.after = full.slice(p);
  st.tap = null;
  clear_filter_cache();
  refresh_cands();
  draw();
}

function draw() {
  draw_buttons();
  draw_text();
}

document.querySelectorAll(".btn").forEach((button) => {
  button.addEventListener("pointerdown", (e) => e.preventDefault()); // keep the caret in the text box
  button.addEventListener("click", () => {
    const row = Number(button.id[0]), col = Number(button.id[1]);
    if (st.expanded) on_expanded(row * 5 + col);
    else if (row === 0) on_candidate(col);
    else on_key(button.id, layout()[row - 1][col]);
    draw();
  });
});

if (is_textarea) {
  for (const ev of ["click", "keyup", "select"]) box.addEventListener(ev, cursor_moved);
  box.focus({ preventScroll: true });
}

addEventListener?.("resize", draw);
document.fonts?.ready.then(draw); // refit once web fonts have loaded

refresh_cands();
draw(); // module scripts run after the page is parsed
