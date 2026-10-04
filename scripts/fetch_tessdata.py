# Fetch Tesseract language packs for offline OCR (hin/mar/guj; eng+osd ship with the binary).
# Usage: python scripts/fetch_tessdata.py [--out tessdata]
# Binary itself: winget install UB-Mannheim.TesseractOCR (or see README).

from __future__ import annotations

import argparse
import os
import sys
import urllib.request

BASE = 'https://github.com/tesseract-ocr/tessdata/raw/main/'
LANGS = ('hin', 'mar', 'guj')


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog='python scripts/fetch_tessdata.py')
    parser.add_argument('--out', default='tessdata')
    parser.add_argument('--langs', default=','.join(LANGS))
    args = parser.parse_args(argv)
    os.makedirs(args.out, exist_ok=True)
    ok = True
    for lang in [p.strip() for p in str(args.langs).split(',') if p.strip()]:
        dest = os.path.join(args.out, lang + '.traineddata')
        if os.path.exists(dest):
            print('exists, skipping: %s' % (dest,))
            continue
        try:
            print('downloading %s ...' % (lang,), flush=True)
            urllib.request.urlretrieve(BASE + lang + '.traineddata', dest)
            print('saved %s (%d KB)' % (dest, os.path.getsize(dest) // 1024))
        except Exception as exc:
            print('ERROR: %s download failed (%s)' % (lang, exc), file=sys.stderr)
            ok = False
    print('NOTE: eng+osd ship with the Tesseract installer; point TESSDATA_PREFIX at %s' % (os.path.abspath(args.out),))
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())

