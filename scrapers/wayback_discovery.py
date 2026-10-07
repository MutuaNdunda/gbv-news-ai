"""Shared bounded waybackpy discovery; publisher modules own routes and extraction."""
from dataclasses import dataclass
from datetime import datetime
import logging
import re
from urllib.parse import unquote_plus, urlsplit, urlunsplit

from scrapers.common import allowed_url, normalize_url

LOGGER = logging.getLogger(__name__)


def term_pattern(terms):
    pieces = []
    for term in dict.fromkeys(term.strip() for term in terms or []):
        if not term:
            raise ValueError('Terms must contain non-whitespace text')
        pieces.append(r'(?:-|%20|\+|\s)+'.join(re.escape(word) for word in term.split()))
    return '(?i).*(?:' + '|'.join(pieces) + ').*' if pieces else None


@dataclass
class ArchiveSource:
    """Module configuration: PUBLISHER_HOSTS, ARCHIVE_PREFIXES, normalize_url,
    is_article, archive_parts, parse and parse_live remain source-owned adapters.
    """
    publisher: object

    @property
    def prefixes(self):
        return self.publisher.ARCHIVE_PREFIXES

    def identity(self, url):
        parts = self.publisher.archive_parts(url)
        original = parts[1] if parts else url
        if not self.publisher.is_article(original):
            raise ValueError('Unsupported article route')
        parsed = urlsplit(self.publisher.normalize_url(original))
        host = self.publisher.PUBLISHER_HOSTS[0].removeprefix('www.')
        # Registered routes identify articles in the path; query strings are
        # replay/tracking variants. Retain queries in provenance, not identity.
        return urlunsplit(('https', host, parsed.path.rstrip('/'), '', ''))

    def accepts_fetch(self, url):
        if allowed_url(url, ('web.archive.org',)) and urlsplit(url).path == '/cdx/search/cdx':
            return True
        return self.publisher.accepts(url)

    def live_fetch(self, url):
        return allowed_url(url, self.publisher.PUBLISHER_HOSTS)


class Discovery:
    """Select one capture per article among a strictly bounded observed cohort.

    Newest/oldest compare all observed capture timestamps. A truncated scan does
    not claim that its selected capture is the newest/oldest in the full archive.
    """
    def __init__(self, adapter, client, *, terms=(), start=None, end=None,
                 selection='newest', max_records=10000, max_requests=20, max_pages=20, urls=None):
        if min(max_records, max_requests, max_pages) < 1 or selection not in ('newest', 'oldest'):
            raise ValueError('Discovery bounds must be positive; selection must be newest/oldest')
        self.adapter, self.client = adapter, client
        self.start, self.end, self.selection = start, end, selection
        self.max_records, self.max_requests, self.max_pages = max_records, max_requests, max_pages
        self.urls = urls
        self.pattern = term_pattern(terms)
        self.stats = dict(records=0, index_requests=0, candidates=0, capture_duplicates=0,
                          invalid_routes=0, index_failures=0, discovery_stop_reason='exhausted',
                          bounds_reached=[], discovery_complete=True)

    def bound(self, reason):
        if reason not in self.stats['bounds_reached']:
            self.stats['bounds_reached'].append(reason)
        self.stats.update(discovery_stop_reason=reason, discovery_complete=False)

    def api(self, query, exact):
        from waybackpy import WaybackMachineCDXServerAPI
        from waybackpy.cdx_utils import full_url, check_for_blocked_site
        discovery = self

        class BoundedCDX(WaybackMachineCDXServerAPI):
            def cdx_api_manager(self, payload, headers):
                payload['showResumeKey'] = 'true'
                seen = set()
                for page in range(discovery.max_pages):
                    remaining = discovery.max_records - discovery.stats['records']
                    if remaining <= 0:
                        discovery.bound('max_records')
                        return
                    if discovery.stats['index_requests'] >= discovery.max_requests:
                        discovery.bound('max_index_requests')
                        return
                    payload['limit'] = str(min(500, remaining))
                    url = full_url(self.endpoint, payload)
                    discovery.stats['index_requests'] += 1
                    response = discovery.client.fetch(url, stage='CDX_INDEX')
                    if response is None:
                        raise RuntimeError('CDX request failed or was access-restricted')
                    check_for_blocked_site(response, query)
                    self.last_api_request_url = url
                    lines = response.text.strip().splitlines()
                    key = None
                    if len(lines) >= 2 and not lines[-2].strip():
                        key = unquote_plus(lines.pop().strip())
                        lines.pop()
                    if len(lines) > remaining:
                        lines = lines[:remaining]
                        discovery.bound('max_records')
                    discovery.stats['records'] += len(lines)
                    LOGGER.info('%s CDX request %d: %d records; continuation=%s',
                                discovery.adapter.publisher.SOURCE, discovery.stats['index_requests'], len(lines), bool(key))
                    yield '\n'.join(lines)
                    if not key:
                        return
                    if key in seen:
                        raise ValueError('Repeated CDX continuation key')
                    seen.add(key)
                    payload['resumeKey'] = key
                discovery.bound('max_pages')

        filters = ['statuscode:200', 'mimetype:text/html']
        if self.pattern:
            filters.append('original:' + self.pattern)
        return BoundedCDX(query, self.client.user_agent, match_type='exact' if exact else 'prefix',
                          start_timestamp=self.start, end_timestamp=self.end, filters=filters, limit='500')

    def in_window(self, timestamp):
        datetime.strptime(timestamp, '%Y%m%d%H%M%S')
        return ((not self.start or timestamp >= self.start.ljust(14, '0'))
                and (not self.end or timestamp <= self.end.ljust(14, '9')))

    def candidates(self):
        selected = {}
        queries = list(dict.fromkeys(self.urls)) if self.urls is not None else self.adapter.prefixes
        for query in queries:
            if self.stats['records'] >= self.max_records:
                self.bound('max_records')
                break
            if self.stats['index_requests'] >= self.max_requests:
                self.bound('max_index_requests')
                break
            parts = self.adapter.publisher.archive_parts(query)
            if parts:
                if not self.adapter.publisher.accepts(query) or not self.in_window(parts[0]):
                    self.stats['invalid_routes'] += 1
                    continue
                self.stats['records'] += 1
                records = [(parts[0], parts[1], query, query)]
            else:
                exact = self.urls is not None
                if exact and not self.adapter.publisher.is_article(query):
                    self.stats['invalid_routes'] += 1
                    continue
                api = self.api(query, exact)
                def records_from_api():
                    for snapshot in api.snapshots():
                        if snapshot.statuscode != '200' or snapshot.mimetype != 'text/html':
                            self.stats['invalid_routes'] += 1
                            continue
                        yield (snapshot.timestamp, snapshot.original,
                               f'https://web.archive.org/web/{snapshot.timestamp}id_/{snapshot.original}',
                               api.last_api_request_url)
                records = records_from_api()
            try:
                for timestamp, original, replay, discovery_url in records:
                    if (not self.adapter.publisher.is_article(original) or not self.in_window(timestamp)
                            or (self.pattern and not re.fullmatch(self.pattern, original))):
                        self.stats['invalid_routes'] += 1
                        continue
                    identity = self.adapter.identity(original)
                    if identity in selected:
                        self.stats['capture_duplicates'] += 1
                    previous = selected.get(identity)
                    if (previous is None or (timestamp > previous[0] if self.selection == 'newest'
                                             else timestamp < previous[0])):
                        selected[identity] = timestamp, replay, discovery_url
            except Exception as exc:
                self.stats['index_failures'] += 1
                self.stats.update(discovery_complete=False, discovery_stop_reason='index_failed')
                LOGGER.warning('%s archive discovery failed (%s); continuing within bounds',
                               self.adapter.publisher.SOURCE, type(exc).__name__)
        self.stats['candidates'] = len(selected)
        if not selected and self.stats['discovery_complete']:
            self.stats['discovery_stop_reason'] = ('no_valid_candidates' if self.stats['records']
                                                  else 'no_coverage_or_matches')
        for timestamp, replay, discovery_url in selected.values():
            yield replay, discovery_url, 'waybackpy_cdx'
