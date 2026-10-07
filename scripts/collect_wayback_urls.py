"""Find an archived Nation article per pasted URL using waybackpy, then collect it."""
import argparse
import logging
import math
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.collect_urls import extract_urls
from scripts.trial_scraper import run_trial_extraction
from scrapers import nation
from scrapers.common import Client
from database.session import load_environment


def resolve_archives(urls, client, selection='newest'):
    """Use waybackpy parsing with the shared bounded, robots-aware HTTP transport."""
    from waybackpy import WaybackMachineCDXServerAPI
    from waybackpy.cdx_utils import full_url
    from waybackpy.exceptions import NoCDXRecordFound

    class BoundedCDX(WaybackMachineCDXServerAPI):
        def cdx_api_manager(self, payload, headers):
            payload['limit'] = '1'
            query = full_url(self.endpoint, payload)
            response = client.fetch(query, stage='CDX_INDEX')
            if response is None:
                raise RuntimeError('Archive lookup failed; rerun later. Existing saved articles are retained.')
            self.last_api_request_url = query
            yield response.text

    archives = []
    for url in urls:
        if nation.accepts(url):
            archives.append(url)
            continue
        api = BoundedCDX(url, client.user_agent, match_type='exact',
                         filters=['statuscode:200', 'mimetype:text/html'])
        try:
            snapshot = getattr(api, selection)()
        except NoCDXRecordFound:
            logging.warning('No successful HTML archive for one input article; skipped')
            continue
        if not nation.accepts(snapshot.archive_url):
            raise ValueError('Archive lookup returned an unsupported article URL')
        archives.append(snapshot.archive_url)
    return list(dict.fromkeys(archives))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--file', type=Path, help='Private plain-text or Markdown URL file')
    parser.add_argument('--url', action='append', default=[], help='Repeatable Nation article URL')
    parser.add_argument('--selection', choices=['newest', 'oldest'], default='newest')
    parser.add_argument('--delay', type=float, default=3)
    parser.add_argument('--run-name')
    parser.add_argument('--dry-run', action='store_true', help='Validate only; no archive lookup or cloud access')
    args = parser.parse_args()
    if not math.isfinite(args.delay) or args.delay < 1.5:
        parser.error('--delay must be finite and at least 1.5 seconds')
    text = '\n'.join(args.url)
    if args.file:
        text += '\n' + args.file.read_text(encoding='utf-8')
    elif not args.url:
        if sys.stdin.isatty():
            print('Paste public Nation article URLs or a Markdown table, then press Ctrl-D:')
        text += '\n' + sys.stdin.read()
    urls, rejected = extract_urls(text)
    print(f'Accepted unique article URLs: {len(urls)}; rejected: {len(rejected)}')
    if rejected:
        print('Sign-in URLs and unsupported routes are skipped; embedded redirect targets are not followed.')
    if not urls:
        return 2
    if args.dry_run:
        return 0
    load_environment()
    logging.basicConfig(level=logging.INFO)
    client = Client(('web.archive.org',), args.delay,
                    os.environ.get('SCRAPER_USER_AGENT', 'GBVResearchBot/0.1'))
    client.source = 'nation'
    try:
        archives = resolve_archives(urls, client, args.selection)
    finally:
        client.session.close()
    print(f'Resolved article replays: {len(archives)}')
    if not archives:
        return 2
    run_trial_extraction(sources=['nation'], input_urls=archives, limit=len(archives),
                         delay=args.delay, run_name=args.run_name)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
