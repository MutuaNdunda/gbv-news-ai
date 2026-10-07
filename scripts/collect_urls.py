"""Collect explicitly supplied public Nation articles, without archive discovery."""
from pathlib import Path
import argparse
import logging
import math
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scrapers import nation
from scrapers.common import normalize_url
from scripts.trial_scraper import run_trial_extraction


def extract_urls(text):
    """Accept plain links or pasted Markdown tables; reject access/login routes."""
    accepted, rejected, seen = [], [], set()
    for value in re.findall(r'https?://[^\s<>"\[\]|]+', text):
        value = value.rstrip(').,;')
        try:
            url = normalize_url(value)
            valid = nation.accepts(url) or nation.is_article(url)
        except ValueError:
            url, valid = value, False
        if url in seen:
            continue
        seen.add(url)
        (accepted if valid else rejected).append(url)
    return accepted, rejected


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, help='Private text/Markdown URL file; otherwise paste into stdin')
    parser.add_argument('--url', action='append', default=[], help='Article URL, repeatable')
    parser.add_argument('--delay', type=float, default=3)
    parser.add_argument('--run-name')
    parser.add_argument('--dry-run', action='store_true', help='Validate input without network or cloud access')
    args = parser.parse_args()
    if not math.isfinite(args.delay) or args.delay < 1.5:
        parser.error('--delay must be finite and at least 1.5 seconds')
    text = '\n'.join(args.url)
    if args.file:
        text += '\n' + args.file.read_text(encoding='utf-8')
    elif not args.url:
        if sys.stdin.isatty():
            print('Paste article URLs or a Markdown table, then press Ctrl-D:')
        text += '\n' + sys.stdin.read()
    urls, rejected = extract_urls(text)
    print(f'Accepted unique article URLs: {len(urls)}; rejected URLs: {len(rejected)}')
    if rejected:
        print('Rejected links include unsupported publishers/routes, sign-in pages or undated archive links. '
              'Login redirect targets are not extracted. Supply public article URLs or dated article replays.')
    if not urls:
        return 2
    if args.dry_run:
        return 0
    logging.basicConfig(level=logging.INFO)
    run_trial_extraction(sources=['nation'], input_urls=urls, limit=len(urls),
                         delay=args.delay, run_name=args.run_name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
