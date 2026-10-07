"""Standalone local Nation archive collection; no app, database or cloud services."""
from pathlib import Path
import argparse
import calendar
from datetime import date, datetime, timezone
import hashlib
import json
import logging
import math
import sys
from urllib.parse import unquote_plus

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scrapers import nation
from scrapers.common import Client

LOGGER = logging.getLogger(__name__)


def months(start, end):
    current = start.replace(day=1)
    while current <= end:
        yield current
        current = date(current.year + (current.month == 12), current.month % 12 + 1, 1)


def publication_date(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).date()
    except (ValueError, TypeError, AttributeError):
        return None


def snapshots(client, month, max_pages):
    """Bound waybackpy continuation requests using the shared requests transport."""
    from waybackpy import WaybackMachineCDXServerAPI
    from waybackpy.cdx_utils import full_url

    class BoundedCDX(WaybackMachineCDXServerAPI):
        def cdx_api_manager(self, payload, headers):
            payload.update(limit='500', showResumeKey='true')
            seen = set()
            for page in range(max_pages):
                query = full_url(self.endpoint, payload)
                response = client.fetch(query, stage='CDX_INDEX')
                if response is None:
                    raise RuntimeError(f'CDX failed for {month:%Y-%m}, page {page + 1}; coverage incomplete')
                self.last_api_request_url = query
                lines = response.text.strip().splitlines()
                key = None
                if len(lines) >= 2 and not lines[-2].strip():
                    key = unquote_plus(lines.pop().strip())
                    lines.pop()
                yield '\n'.join(lines)
                if not key:
                    return
                if key in seen:
                    raise RuntimeError('Repeated CDX continuation key; coverage incomplete')
                seen.add(key)
                payload['resumeKey'] = key
            raise RuntimeError(f'CDX page bound reached for {month:%Y-%m}; coverage incomplete. Increase --max-pages.')

    last = calendar.monthrange(month.year, month.month)[1]
    api = BoundedCDX('https://nation.africa/kenya/', client.user_agent,
                     match_type='prefix', start_timestamp=f'{month:%Y%m}01',
                     end_timestamp=f'{month:%Y%m}{last:02d}',
                     filters=['statuscode:200', 'mimetype:text/html'], collapses=['urlkey'])
    for snapshot in api.snapshots():
        yield snapshot, api.last_api_request_url


def collect(args):
    output = args.output.resolve()
    if not output.is_relative_to(ROOT / 'data'):
        raise ValueError('--output must be inside repository data/ to keep collected material out of Git')
    raw_dir = output / 'raw'
    raw_dir.mkdir(parents=True, exist_ok=True)
    records = output / 'articles.jsonl'
    urls, hashes = set(), set()
    if records.exists():
        for line in records.read_text(encoding='utf-8').splitlines():
            article = json.loads(line)
            urls.add(article['canonical_url'])
            hashes.add(article['content_hash'])
    index = Client(('web.archive.org',), args.delay, args.user_agent,
                   read_timeout=args.index_read_timeout)
    replay = Client(nation.HOSTS, args.delay, args.user_agent, url_validator=nation.accepts)
    index.source = replay.source = 'nation'
    summary = {'started_at': datetime.now(timezone.utc).isoformat(),
               'publication_start': str(args.start), 'publication_end': str(args.end),
               'status': 'running', 'saved': 0, 'attempted': 0, 'missing_date': 0,
               'outside_window': 0, 'inaccessible': 0, 'scans': {}}
    try:
        for month in months(args.start, args.end):
            summary['scans'][f'{month:%Y-%m}'] = 'running'
            LOGGER.info('Discovering Nation captures for %s', month.strftime('%Y-%m'))
            for snapshot, discovery in snapshots(index, month, args.max_pages):
                if not nation.is_article(snapshot.original) or snapshot.original in urls:
                    continue
                summary['attempted'] += 1
                archive = f'https://web.archive.org/web/{snapshot.timestamp}id_/{snapshot.original}'
                response = replay.fetch(archive, stage='ARTICLE_FETCH')
                if response is None or 'html' not in response.headers.get('Content-Type', '').lower():
                    summary['inaccessible'] += 1
                    continue
                digest = hashlib.sha256(response.content).hexdigest()
                raw_path = raw_dir / f'{digest}.html'
                if not raw_path.exists():
                    raw_path.write_bytes(response.content)
                    raw_path.with_suffix('.meta.json').write_text(json.dumps({
                        'requested_url': archive, 'actual_url': response.url,
                        'discovery_url': discovery, 'http_status': response.status_code,
                        'retrieved_at': datetime.now(timezone.utc).isoformat()}, indent=2), encoding='utf-8')
                article = nation.parse(response.content, response.url)
                if not article:
                    summary['inaccessible'] += 1
                    continue
                published = publication_date(article.get('published_at'))
                if published is None:
                    summary['missing_date'] += 1
                    continue
                if not args.start <= published <= args.end:
                    summary['outside_window'] += 1
                    continue
                if article['canonical_url'] in urls or article['content_hash'] in hashes:
                    continue
                article.update(requested_url=archive, discovery_url=discovery,
                               discovery_method='waybackpy_cdx', raw_path=str(raw_path),
                               http_status=response.status_code)
                with records.open('a', encoding='utf-8') as handle:
                    handle.write(json.dumps(article, ensure_ascii=False) + '\n')
                urls.add(article['canonical_url'])
                hashes.add(article['content_hash'])
                summary['saved'] += 1
                LOGGER.info('Saved %d new articles', summary['saved'])
                if summary['saved'] >= args.limit:
                    summary['status'] = 'limit_reached'
                    summary['scans'][f'{month:%Y-%m}'] = 'incomplete_limit'
                    return summary
            summary['scans'][f'{month:%Y-%m}'] = 'index_exhausted'
        summary['status'] = 'finished'
        return summary
    except BaseException:
        summary['status'] = 'failed_or_interrupted'
        raise
    finally:
        index.session.close()
        replay.session.close()
        summary['finished_at'] = datetime.now(timezone.utc).isoformat()
        (output / 'last_run.json').write_text(json.dumps(summary, indent=2), encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--start', type=date.fromisoformat, default=date(2026, 1, 1))
    parser.add_argument('--end', type=date.fromisoformat, default=date(2026, 8, 31))
    parser.add_argument('--limit', type=int, default=1000, help='Maximum new articles saved this invocation')
    parser.add_argument('--max-pages', type=int, default=20, help='Maximum 500-row CDX pages per capture month')
    parser.add_argument('--delay', type=float, default=3)
    parser.add_argument('--index-read-timeout', type=float, default=60)
    parser.add_argument('--user-agent', default='GBVResearchBot/0.1')
    parser.add_argument('--output', type=Path, default=ROOT / 'data/trials/nation-wayback-2026')
    args = parser.parse_args()
    if (args.start > args.end or args.limit < 1 or args.max_pages < 1
            or not math.isfinite(args.delay) or args.delay < 1.5
            or not math.isfinite(args.index_read_timeout) or not 1 <= args.index_read_timeout <= 300):
        parser.error('Invalid dates/limits/timeouts; delay must be at least 1.5 seconds')
    logging.basicConfig(level=logging.INFO)
    try:
        summary = collect(args)
    except (RuntimeError, ValueError) as exc:
        LOGGER.error('%s', exc)
        return 2
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
