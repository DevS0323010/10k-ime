# 10k-IME

A Traditional Chinese (Zhuyin) and English input method that runs in the browser and types everything with **10 keys**: no chords, one key at a time, with word prediction. English letters sit on 7 of those keys.

## Live demo

<https://devs0323010.github.io/10k-ime/>

## Overview

This is a web-based IME: no native SDK, no app store, no build step. Open the page and start typing.

| Language | Keys | Approach |
|----------|------|----------|
| English | 10 keys: 7 letter-group keys + Fn, Space, ⌫ | One press per letter, then pick the word. Ranked by word frequency blended with the previous word (bigrams) |
| Traditional Chinese | The same 10 keys, relabelled at each step (Zhuyin/Bopomofo) | Consonant → vowel → coda/tone, then pick the character or word. Ranked by frequency blended with the text already typed |

## Webapp & UI

### Layout

The screen has a text box on top, then a **3×5 grid**: one row of 5 candidates and two rows of 5 keys. The text box takes about 36% of the screen height (26% on short landscape screens), and the grid fills the rest, so it can be used with one thumb on a phone.

### Candidate bar & expanded list

Every key press updates the candidates. The first slot (shown in blue) is the best word whose code matches the keys exactly; the others are the remaining exact matches and up to 5 longer words, sorted together. **Space** commits the first candidate, and tapping any slot commits that one.

When there are more than 5 candidates, the 5th slot becomes **…**. It opens the full list over the keys: 4 candidates per row on all 3 rows (12 per page), with the right column used for **✕** (collapse), **▲** (previous page) and **▼** (next page).

### English mode

- **One press per letter**: the letter keys are `abcd` `efgh` `ijksz` `lmn` `opqr` `t` `uvwxy`. Press one key per letter and pick the word, like T9. While a word is being typed, the Fn corner becomes `'-` for apostrophes and hyphens.
- **Prediction**: candidates blend word frequency with how often each word follows the previous one (weight 0.7 on the bigram). With nothing typed, the bar shows next-word guesses.
- **Smart capitalization**: the first word of a sentence is capitalized, and so is the word after Mr., Mrs., Ms. and Dr. A period after one of these titles doesn't end the sentence, and the word after St., Jr., Sr. or vs. is not capitalized.
- **Caps (⇧)**: cycles lowercase → Title (next word only) → ALL CAPS. The letter keys show the current state (abcd / Abcd / ABCD).
- **Backspace**: deletes the last key of the word being typed. With nothing being typed, it deletes a whole English word before the cursor (or one character of Chinese or punctuation).

### Fn menu (both languages)

Fn opens: ↵ new line, **?!** punctuation, **🌐** switch language, ⌧ clear, **123** numbers, **abc…** single letters (Chinese: **ㄅㄆㄇ…** and **ㄚㄛㄜ…** single Zhuyin), ⇧ caps (English only), ⧉ copy to clipboard, and 🔊 read aloud. ⇧ and 🔊 keep the menu open so they can be pressed again; ✕ in the same corner closes it.

### Multi-tap modes

Single letters, punctuation, numbers and single Zhuyin use multi-tap with **no timer**:

- Pressing the same key again always cycles to its next character.
- Space or any other key confirms the waiting character (Space confirms without adding a space).
- ⌫ removes the waiting character, or otherwise deletes exactly one character.
- **Brackets and quotes** are not closed automatically. If a bracket is open, the bracket key offers the closing one first. The 「」 key closes an open quote first and cycles through 『』.

### Chinese mode (Zhuyin / Bopomofo)

- **Stage-based input**: the keys relabel after each press.
  1. **Consonant group**: ㄅ / ㄉ / ㄍ / ㄐㄗ / ㄓ on the bottom row, then the exact initial on the top row. ㄐㄗ, ㄑㄘ and ㄒㄙ share a key, and **Ø** means no initial.
  2. **Vowel**: ㄚ, ㄧㄚ, ㄨㄚ, ㄩ, ㄛ/ㄜ, ㄧㄝ, ㄨㄛ, ㄩㄝ, ㄭ/ㄦ.
  3. **Coda and tone**: the top row shows the codas for that vowel (for example ㄞ ㄠ ㄢ ㄤ after ㄚ) and the bottom row the five tones **ˇ ˋ ˊ ˙ ˉ**. ˉ is its own key for the first tone. A tone finishes the syllable.
- **Coda fallbacks**: a vowel and coda that don't form a real final go to the closest one (for example ㄨㄚ + ㄨ → ㄨ).
- **Clean composition text**: the text box shows only readings that can occur. ㄐㄗ + ㄧ/ㄧㄞ + ˋ shows as ㄐㄧˋ.
- **Context prediction**: candidates use the end of the committed text (up to 4 characters) to predict the next characters. While a syllable is unfinished, up to 45 candidates are offered for the expanded list.
- **Backspace**: steps back one stage at a time while composing, then deletes one character.
- **CJK punctuation**: the **?!** key (on the first Chinese stage and in Fn) has ，、。…：；！？—～《》「」『』（）.
- **Single Zhuyin**: Fn → ㄅㄆㄇ… and ㄚㄛㄜ… type individual Zhuyin and tone marks with multi-tap.

### Read aloud

🔊 picks the voice from the text, not the current mode: Chinese parts are read with a zh-TW voice and English parts with an en-US voice, in order. Pressing it again restarts the reading. It uses the browser's built-in speech voices.

### Theming

Colors are CSS custom properties with a **light** and a **dark** palette (picked by `prefers-color-scheme`). Keys are colored by what they do:

- English letter keys and Zhuyin consonant groups: light blue
- Vowels: purple · Codas: green · Tones: amber · Punctuation: teal
- Fn and ✕ (top-left corner): solid blue
- Keys that open a menu (123, ?!, abc…, …, ▼): slate
- Keys that change the text right away (⌫, ↵, ⌧): red
- Keys that leave the text alone (⇧, ⧉, 🔊, 🌐): light gray

No fonts are downloaded. Latin text uses a font already on the device where capital I and small l look different (Verdana or Tahoma, else a built-in monospace font), and a `@font-face` with `local()` draws the tone marks from an installed CJK font.

### Mobile-first

- `touch-action: manipulation` disables double-tap zoom during fast typing, and holding a key doesn't select text.
- `100dvh` and `env(safe-area-inset-bottom)` handle iOS Safari's address bar and home-indicator area.
- The phone keyboard never opens. Tap the text to move the cursor; the cursor is drawn by the page and doesn't blink.

## How it works

The app is a single-page JavaScript application served directly from the repository, with no build step.

```
runner/
  main.js          # Entry point, UI, key handling and drawing
  maps.js          # Key layouts and code tables for English and Chinese
  ranker.js        # Candidate ranking (en_rank, zh_rank)
  read_data.js     # Loads the curated JSON, binary-search lookups
```

The curated data files (`data/curated/en_keyed.json`, `data/curated/zh_keyed.json`) are committed to the repo, so the app works as soon as it is served from GitHub Pages. They already hold every word under its key code, sorted, so the browser only parses them:

- `en_keyed.json`: English word counts by key code, and bigrams (which words follow each word) for next-word prediction.
- `zh_keyed.json`: characters and words by key code, and the list of multi-character phrases for next-character prediction.

## Project structure

```
10k-ime/
├── data/
│   ├── raw/          # Downloaded corpora (not needed for the web app)
│   └── curated/      # en_keyed.json, zh_keyed.json (committed)
├── loader/           # Python: download corpora, build the curated JSON
├── optimizer/        # Python: layout search and ranking tuning
├── runner/           # JavaScript: the web app
├── stylesheets/      # CSS
├── index.html        # Entry point
├── THIRD_PARTY_NOTICES.md
└── pyproject.toml    # Project metadata (Python >= 3.12)
```

## Getting started

Serve the folder over HTTP. The app loads its JSON with ES module imports, so opening `index.html` directly (`file://`) fails.

```sh
python -m http.server
# Visit http://localhost:8000
```

Or visit the [live demo](https://devs0323010.github.io/10k-ime/).

The JSON imports use import attributes (`with { type: "json" }`), so a recent browser is needed: Chrome/Edge 123+, Safari 17.2+ or Firefox 138+.

The curated data files are committed, so the app works as-is. To rebuild them from the raw corpora (optional; the scripts use only the Python standard library):

```sh
# English
python loader/download_data.py
python loader/get_sequences.py           # -> data/curated/en_keyed.json

# Chinese
python loader/download_chinese.py
python loader/get_chinese_sequences.py   # -> data/curated/zh_keyed.json
```

## Data pipeline

- **English**: reads the Tatoeba English sentences, counts words and bigrams, and writes each word under its 7-key code. A period after a title such as "Mr." is not treated as a sentence end. Rare words are dropped, rare bigrams are filtered, and a few stock names (Tom, Mary, …) are capped to keep the data small.
- **Chinese**: combines McBopomofo's word frequencies with its Zhuyin readings and writes every character and word under the 10-key code of its reading (initial + final + tone, per syllable). A character with several readings keeps the full count for its usual reading, 1/10 for the second and 1/100 for others. Only Big5 characters are kept. Dictionary words never seen in the corpus are kept with a count of 0.

## Layout optimization and tuning

`optimizer/` holds Python tools (standard library only):

- `tune_en_rank.py`: replays real sentences through a Python copy of `en_rank` to tune the ranking settings. It reads the same `data/curated/en_keyed.json` as the web app, for example `python optimizer/tune_en_rank.py --sentences data/raw/tatoeba/eng_sentences.tsv`.
- `optimize_layout.py` (**obsolete**): the search that picked the English letter layout, using simulated annealing and hill climbing scored by collisions between common words and keypresses per letter (KPL). It reads `data/unigrams.tsv` and `data/bigrams.tsv`, which the pipeline no longer produces and which have been removed, so it does not run as-is. It is kept as a record of how the layout was chosen.

The chosen layout and settings are already in the web app. `tune_en_rank.py` can recheck the ranking settings if the corpora change.

## License

This project is licensed under the **GNU General Public License v3.0** (GPLv3).

The data files are derived from third-party sources that keep their own licenses:

| Data | Built from | License |
|------|-----------|---------|
| `en_keyed.json` (English words & bigrams) | [Tatoeba](https://tatoeba.org) English sentences | [CC BY 2.0 FR](https://creativecommons.org/licenses/by/2.0/fr/) (the CC0 subset is [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)) |
| `zh_keyed.json` (Traditional Chinese characters & words) | [McBopomofo](https://github.com/openvanilla/McBopomofo) dictionary data | [MIT](https://opensource.org/licenses/MIT) |

Full attribution and license text for each source is in [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) and must be kept with any copy of the data files.
