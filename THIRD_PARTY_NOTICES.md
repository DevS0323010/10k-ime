# Third-Party Notices

This project is licensed under the GNU General Public License v3.0 (GPLv3).
Its word lists are built from the third-party data listed below. That data
keeps its own license, and the notices below must be kept with any copy of the
data files.

| Data file | Built from | License |
|---|---|---|
| `words.json`, `bigrams.json` (English) | Tatoeba English sentences | CC BY 2.0 FR (the CC0 subset is CC0 1.0) |
| `zh_words.json`, `zh_ngrams.json` (Traditional Chinese) | McBopomofo dictionary data | MIT |

---

## 1. Tatoeba

- Source: https://tatoeba.org
- Download: https://downloads.tatoeba.org/exports/per_language/eng/
  (`eng_sentences.tsv.bz2`, fetched by `scripts/download_data.py`)
- License: Creative Commons Attribution 2.0 France (CC BY 2.0 FR),
  https://creativecommons.org/licenses/by/2.0/fr/
  Sentences in `eng_sentences_CC0.tsv.bz2` (the `--cc0` option) are released
  under CC0 1.0, https://creativecommons.org/publicdomain/zero/1.0/
- Copyright: the individual Tatoeba contributors.

Changes made: the sentences are not redistributed. The English word and
word-pair (bigram) frequency counts in `words.json` and `bigrams.json` were
computed from them: the text was split into words, punctuation and accents
were removed, rare words were dropped and a few stock names were capped.

> English word and bigram frequencies derived from sentences by the
> contributors of Tatoeba (https://tatoeba.org), licensed under CC BY 2.0 FR
> (https://creativecommons.org/licenses/by/2.0/fr/).

---

## 2. McBopomofo (小麥注音輸入法)

- Source: https://github.com/openvanilla/McBopomofo
- Files used (fetched by `scripts/download_chinese.py`):
  `Source/Data/phrase.occ`, `Source/Data/BPMFBase.txt`,
  `Source/Data/BPMFMappings.txt`, `Source/Data/heterophony1.list`,
  `Source/Data/heterophony2.list`
- License: MIT License (full text below). McBopomofo notes that its phrase list
  (`BPMFMappings.txt`) was originally derived from the `tsi.src` file of
  libtabe (BSD licensed).

Changes made: `zh_words.json` and `zh_ngrams.json` combine McBopomofo's word
frequencies with its Zhuyin readings. Words with non-Big5 characters were
removed, words are grouped by pronunciation, and the counts of secondary
readings of single characters were scaled down.

```
MIT License

Copyright (c) 2011-2026 Mengjuei Hsieh et al.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
