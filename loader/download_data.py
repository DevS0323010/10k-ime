#!/usr/bin/env python3
"""Download the English sentence data for the 10-key IME. Standard library only.

Usage:
  python download_data.py           # all Tatoeba English sentences (~25 MB download)
  python download_data.py --cc0     # public-domain (CC0) subset only (~1.3 MB download)
  python download_data.py --out DIR # save somewhere other than data/raw

The file is downloaded, decompressed to a plain .tsv, and the .bz2 is removed.
Each line of the .tsv is: id<TAB>lang<TAB>sentence
Word frequencies and bigrams are both counted from these sentences.

If the .tsv already exists it is skipped. A stopped download resumes,
so you can re-run the same command any time.

License (keep this credit in your NOTICE file):
  Tatoeba (https://tatoeba.org): CC BY 2.0 FR; the --cc0 file is CC0 1.0.
"""
import argparse
import bz2
import os
import shutil
import sys
import urllib.error
import urllib.request

DEFAULT_OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "raw")

TATOEBA_BASE = "https://downloads.tatoeba.org/exports/per_language/eng/"
TATOEBA_FULL = "eng_sentences.tsv.bz2"
TATOEBA_CC0 = "eng_sentences_CC0.tsv.bz2"


def download(url, dest):
    """Download url to dest, resuming a partial file. Returns True on success."""
    part = dest + ".part"
    done = os.path.getsize(part) if os.path.exists(part) else 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={done}-"} if done else {})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            if done and resp.status != 206:  # server ignored Range, start over
                done = 0
            total = resp.headers.get("Content-Length")
            total = int(total) + done if total else None
            with open(part, "ab" if done else "wb") as f:
                while True:
                    chunk = resp.read(1 << 20)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if total:
                        print(f"\r  {done / 1e6:8.1f} / {total / 1e6:.1f} MB", end="", flush=True)
        print()
    except urllib.error.HTTPError as e:
        if e.code != 416:  # 416 = range past end: file is already complete
            print(f"\n  failed: HTTP {e.code}")
            return False
    except (urllib.error.URLError, OSError) as e:
        print(f"\n  failed: {e} (re-run to resume)")
        return False
    os.replace(part, dest)
    return True


def decompress(src, dest):
    """Unpack a .bz2 file to dest, then delete the .bz2. Returns True on success."""
    print(f"unpack {os.path.basename(src)}")
    tmp = dest + ".part"
    try:
        with bz2.open(src, "rb") as fin, open(tmp, "wb") as fout:
            shutil.copyfileobj(fin, fout, 1 << 20)
    except (OSError, EOFError) as e:
        # A broken archive: remove it so the next run downloads it again.
        print(f"  failed: {e} (re-run to download again)")
        for p in (tmp, src):
            if os.path.exists(p):
                os.remove(p)
        return False
    os.replace(tmp, dest)
    os.remove(src)
    return True


def get_sentences(out_dir, cc0):
    folder = os.path.join(out_dir, "tatoeba")
    os.makedirs(folder, exist_ok=True)
    name = TATOEBA_CC0 if cc0 else TATOEBA_FULL
    archive = os.path.join(folder, name)
    tsv = archive[: -len(".bz2")]

    if os.path.exists(tsv):
        print(f"skip {os.path.basename(tsv)} (already there)")
        return True
    if not os.path.exists(archive):
        print(f"get  {name}")
        if not download(TATOEBA_BASE + name, archive):
            return False
    if not decompress(archive, tsv):
        return False
    print(f"saved {tsv}")
    return True


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cc0", action="store_true", help="get only the public-domain (CC0) sentences")
    p.add_argument("--out", default=DEFAULT_OUT, help="output folder (default: data/raw next to scripts/)")
    a = p.parse_args()

    ok = get_sentences(os.path.abspath(a.out), a.cc0)
    print("done" if ok else "download failed; re-run the same command to retry")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
