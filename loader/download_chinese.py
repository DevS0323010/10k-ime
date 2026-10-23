#!/usr/bin/env python3
"""Download the Traditional Chinese (Taiwan) word data for the 10-key IME. Standard library only.

Usage:
  python download_chinese.py           # McBopomofo word list, readings and counts (~9 MB)
  python download_chinese.py --out DIR # save somewhere other than data/raw

The files come from the McBopomofo (小麥注音) input method and are saved to
data/raw/mcbopomofo/:
  phrase.occ          word<SPACE>count    (how often each word appears in a large
                                           Taiwanese text corpus)
  BPMFBase.txt        char<SPACE>zhuyin<SPACE>pinyin<SPACE>...   (single characters)
  BPMFMappings.txt    word<SPACE>zhuyin syllables ...            (2-6 character words)
  heterophony1.list   char<SPACE>zhuyin   (the usual reading of a char with several)
  heterophony2.list   char<SPACE>zhuyin   (its second most usual reading)
  LICENSE.txt

Run get_chinese_words.py afterwards to turn them into data/zh_unigrams.tsv.

Files that already exist are skipped. A stopped download resumes,
so you can re-run the same command any time.

License (keep this credit in your NOTICE file):
  McBopomofo data (https://github.com/openvanilla/McBopomofo): MIT License,
  Copyright (c) 2011-2026 Mengjuei Hsieh et al. MIT is compatible with GPLv3.
"""
import argparse
import os
import sys

from download_data import download

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")

# Pinned to the master branch. Change "master" to a commit id to freeze the data.
MCBOPOMOFO_BASE = "https://raw.githubusercontent.com/openvanilla/McBopomofo/master/"
MCBOPOMOFO_FILES = [
    "Source/Data/phrase.occ",
    "Source/Data/BPMFBase.txt",
    "Source/Data/BPMFMappings.txt",
    "Source/Data/heterophony1.list",
    "Source/Data/heterophony2.list",
    "LICENSE.txt",
]


def get_mcbopomofo(out_dir):
    folder = os.path.join(out_dir, "mcbopomofo")
    os.makedirs(folder, exist_ok=True)
    ok = True
    for path in MCBOPOMOFO_FILES:
        name = os.path.basename(path)
        dest = os.path.join(folder, name)
        if os.path.exists(dest):
            print(f"skip {name} (already there)")
            continue
        print(f"get  {name}")
        if not download(MCBOPOMOFO_BASE + path, dest):
            ok = False
    if ok:
        print(f"saved {folder}")
    return ok


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", default=DEFAULT_OUT, help="output folder (default: data/raw next to scripts/)")
    a = p.parse_args()

    ok = get_mcbopomofo(os.path.abspath(a.out))
    print("done" if ok else "download failed; re-run the same command to retry")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
