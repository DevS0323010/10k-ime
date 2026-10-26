// Key tables for the 10-key IME. Buttons: row 1 = ids "10".."14", row 2 = "20".."24".
// Codes here must match get_sequences.py (English) and get_chinese_sequences.py (Chinese).

// ------------------------------------------------------------ word codes

// English letter -> key digit ("-" = the Fn key inside a word).
export const en_maps = {
  a: "1", b: "1", c: "1", d: "1",
  e: "2", f: "2", g: "2", h: "2",
  i: "3", j: "3", k: "3", s: "3", z: "3",
  l: "4", m: "4", n: "4",
  o: "5", p: "5", q: "5", r: "5",
  t: "6",
  u: "7", v: "7", w: "7", x: "7", y: "7",
  "'": "-", "-": "-",
};

// Vowel key + coda key (.1-.4) -> code of the final. Cells that don't exist
// point to the final the user most likely meant (ㄨㄚ+.2 = ㄨ, ㄩ+.1 = ㄩ ...).
// Ø + ㄧㄚ + .1 is both ㄧ ("61") and ㄧㄞ ("21", 崖); main.js searches both.
export const zh_vowel_fallback = {
  1: { 1: "11", 2: "12", 3: "13", 4: "14" },
  5: { 1: "51", 2: "52", 3: "53", 4: "54" },
  2: { 1: "61", 2: "22", 3: "23", 4: "24" },
  6: { 1: "61", 2: "62", 3: "63", 4: "64" },
  3: { 1: "31", 2: "72", 3: "33", 4: "34" },
  7: { 1: "71", 2: "72", 3: "73", 4: "74" },
  4: { 1: "4", 2: "4", 3: "43", 4: "84" },
  8: { 1: "4", 2: "4", 3: "83", 4: "84" },
};

// ------------------------------------------------------------ Chinese main layout

// Bottom row in the consonant stages: 5 groups; each group's 4 keys go on the top row.
export const zh_groups = [
  { label: "ㄅ", code: "1", members: [["ㄅ", "11"], ["ㄆ", "12"], ["ㄇ", "13"], ["ㄈ", "14"]] },
  { label: "ㄉ", code: "2", members: [["ㄉ", "21"], ["ㄊ", "22"], ["ㄋ", "23"], ["ㄌ", "24"]] },
  { label: "ㄍ", code: "3", members: [["ㄍ", "31"], ["ㄎ", "32"], ["ㄏ", "33"], ["Ø", "60"]] },
  { label: "ㄐㄗ", code: "4", members: [["ㄐㄗ", "41"], ["ㄑㄘ", "42"], ["ㄒㄙ", "43"], ["Ø", "60"]] },
  { label: "ㄓ", code: "5", members: [["ㄓ", "51"], ["ㄔ", "52"], ["ㄕ", "53"], ["ㄖ", "54"]] },
];
export const ZH_NO_INITIAL = "60";

// Vowel stage: top row keys 0-3, bottom row keys 0-4. codas = labels of .1-.4.
export const zh_vowels = [
  [
    { label: "ㄚ", code: "1", codas: ["ㄞ", "ㄠ", "ㄢ", "ㄤ"] },
    { label: "ㄧㄚ", code: "2", codas: ["ㄧ/ㄧㄞ", "ㄧㄠ", "ㄧㄢ", "ㄧㄤ"] },
    { label: "ㄨㄚ", code: "3", codas: ["ㄨㄞ", "ㄨ", "ㄨㄢ", "ㄨㄤ"] },
    { label: "ㄩ", code: "4", codas: ["ㄩ", "ㄩ", "ㄩㄢ", "ㄩㄥ"] },
  ],
  [
    { label: "ㄛ/ㄜ", code: "5", codas: ["ㄟ", "ㄡ", "ㄣ", "ㄥ"] },
    { label: "ㄧㄝ", code: "6", codas: ["ㄧ", "ㄧㄡ", "ㄧㄣ", "ㄧㄥ"] },
    { label: "ㄨㄛ", code: "7", codas: ["ㄨㄟ", "ㄨ", "ㄨㄣ", "ㄨㄥ"] },
    { label: "ㄩㄝ", code: "8", codas: ["ㄩ", "ㄩ", "ㄩㄣ", "ㄩㄥ"] },
    { label: "ㄭ/ㄦ", code: "9", codas: null }, // no coda: straight to the tones
  ],
];
export const zh_vowel_by_code = Object.fromEntries(zh_vowels.flat().map((v) => [v.code, v]));

// Tone row (大千 number-row order, ˉ in the space position).
export const zh_tones = [["ˇ", "a"], ["ˋ", "b"], ["ˊ", "c"], ["˙", "d"], ["ˉ", "e"]];

// ------------------------------------------------------------ static layouts

// act: what the key does in main.js; val: its data.
//   key     add a code digit (English)       tap   multi-tap punctuation (spacing rules)
//   raw     multi-tap, inserted as is        pair  bracket pair, close one if open
//   letter  multi-tap letter (caps applies)  mode / exit / lang / caps / newline / clear / copy / tts
const K = (label, act, val) => ({ label, act, val });
// Keys that do the same thing in English and Chinese share one symbol label.
export const SYM = {
  exit: "✕", space: "␣", bs: "⌫", fn: "Fn", newline: "↵", punc: "?!", lang: "🌐\uFE0E",
  clear: "⌧", number: "123", caps: "⇧", caps_lock: "⇪", copy: "⧉", tts: "🔊\uFE0E",
};
const EXIT = K(SYM.exit, "exit"), SPACE = K(SYM.space, "space"), BS = K(SYM.bs, "bs");
const NEWLINE = K(SYM.newline, "newline"), LANG = K(SYM.lang, "lang"), CLEAR = K(SYM.clear, "clear");
const NUMBER_MODE = K(SYM.number, "mode", "number"), COPY = K(SYM.copy, "copy"), TTS = K(SYM.tts, "tts");

const NUMBER = [
  [EXIT, SPACE, K("+ -", "raw", ["+", "-"]), K(". :", "raw", [".", ":"]), BS],
  [K("1 2", "raw", ["1", "2"]), K("3 4", "raw", ["3", "4"]), K("5 6", "raw", ["5", "6"]),
   K("7 8", "raw", ["7", "8"]), K("9 0", "raw", ["9", "0"])],
];

export const en_layouts = {
  main: [
    [K(SYM.fn, "fn"), SPACE, K("ABCD", "key", "1"), K("EFGH", "key", "2"), BS],
    [K("IJKSZ", "key", "3"), K("LMN", "key", "4"), K("OPQR", "key", "5"), K("T", "key", "6"), K("UVWXY", "key", "7")],
  ],
  fn: [
    [EXIT, NEWLINE, K(SYM.punc, "mode", "punc"), LANG, CLEAR],
    [NUMBER_MODE, K("abc…", "mode", "ts"), K(SYM.caps, "caps"), COPY, TTS],
  ],
  punc: [
    [EXIT, K(",", "tap", [","]), K(". …", "tap", [".", "…"]), K(": ;", "tap", [":", ";"]), BS],
    [K("! ?", "tap", ["!", "?"]), K("- ~", "tap", ["-", "~"]), K("< >", "pair", ["<", ">"]),
     K("' \"", "tap", ["'", '"']), K("( )", "pair", ["(", ")"])],
  ],
  number: NUMBER,
  ts: [ // type single letters
    [EXIT, SPACE, K("abcd", "letter", ["a", "b", "c", "d"]), K("efgh", "letter", ["e", "f", "g", "h"]), BS],
    [K("ijksz", "letter", ["i", "j", "k", "s", "z"]), K("lmn", "letter", ["l", "m", "n"]),
     K("opqr", "letter", ["o", "p", "q", "r"]), K("t", "letter", ["t"]), K("uvwxy", "letter", ["u", "v", "w", "x", "y"])],
  ],
};

export const zh_layouts = {
  fn: [
    [EXIT, NEWLINE, K(SYM.punc, "mode", "punc"), LANG, CLEAR],
    [NUMBER_MODE, K("ㄅㄆㄇ…", "mode", "ts_consonant"), K("ㄚㄛㄜ…", "mode", "ts_vowel"), COPY, TTS],
  ],
  punc: [
    [EXIT, K("，、", "tap", ["，", "、"]), K("。…", "tap", ["。", "…"]), K("：；", "tap", ["：", "；"]), BS],
    [K("！？", "tap", ["！", "？"]), K("—～", "tap", ["—", "～"]), K("《 》", "pair", ["《", "》"]),
     K("「」", "quote"), K("（）", "pair", ["（", "）"])],
  ],
  number: NUMBER,
  ts_consonant: [ // type single Zhuyin consonants
    [EXIT, SPACE, K(SYM.punc, "mode", "punc"), K("", "none"), BS],
    [K("ㄅㄆㄇㄈ", "raw", ["ㄅ", "ㄆ", "ㄇ", "ㄈ"]), K("ㄉㄊㄋㄌ", "raw", ["ㄉ", "ㄊ", "ㄋ", "ㄌ"]),
     K("ㄍㄎㄏ", "raw", ["ㄍ", "ㄎ", "ㄏ"]), K("ㄐㄑㄒㄗㄘㄙ", "raw", ["ㄐ", "ㄑ", "ㄒ", "ㄗ", "ㄘ", "ㄙ"]),
     K("ㄓㄔㄕㄖ", "raw", ["ㄓ", "ㄔ", "ㄕ", "ㄖ"])],
  ],
  ts_vowel: [ // type single Zhuyin vowels and tones
    [EXIT, SPACE, K("ㄧㄨㄩ", "raw", ["ㄧ", "ㄨ", "ㄩ"]), K("", "none"), BS],
    [K("ㄚㄛㄜㄝ", "raw", ["ㄚ", "ㄛ", "ㄜ", "ㄝ"]), K("ㄞㄟㄠㄡ", "raw", ["ㄞ", "ㄟ", "ㄠ", "ㄡ"]),
     K("ㄢㄣㄤㄥ", "raw", ["ㄢ", "ㄣ", "ㄤ", "ㄥ"]), K("ㄦㄭ", "raw", ["ㄦ", "ㄭ"]),
     K("ˇˋˊ˙ˉ", "raw", ["ˇ", "ˋ", "ˊ", "˙", "ˉ"])],
  ],
};

// 「」 key: an open quote makes the close one the first tap; more taps cycle.
export const zh_quote_cycles = {
  none: ["「", "『", "』", "」"],
  "「": ["」", "『", "』", "「"],
  "『": ["』", "「", "」", "『"],
};

// ------------------------------------------------------------ English case rules

// "Mr. Smith": a name follows, so capitalize. After these, don't (1st St., Jr., vs.).
export const EN_NO_CAPITAL_AFTER = new Set(["vs", "jr", "sr", "st"]);
// A period after these does not end the sentence (same list as get_sequences.py).
export const EN_TITLES = new Set(["mr", "mrs", "ms", "dr", "st", "jr", "sr", "vs"]);
