"""Shared normalization and conservative HTTP access for trial scrapers."""
import hashlib
import json
import logging
import time
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

LOGGER = logging.getLogger(__name__)
PARSER_VERSION = '1.0'


def normalize_url(url):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        return ''
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path or '/', parts.query, ''))


def allowed_url(url, hosts):
    try:
        parts = urlsplit(url)
        return bool(normalize_url(url)) and parts.hostname in hosts and parts.port in (None, 80, 443)
    except ValueError:
        return False


class Client:
    """Check robots, throttle all requests, and validate each redirect before fetching."""
    def __init__(self, hosts, delay=2.0, user_agent='GBVResearchBot/0.1',
                 url_validator=None, request_stage='http'):
        self.hosts = hosts
        self.delay = delay
        self.user_agent = user_agent
        self.url_validator = url_validator
        self.request_stage = request_stage
        self.session = requests.Session()
        self.session.headers['User-Agent'] = user_agent
        self.robots = {}
        self.last_request = 0.0
        self.last_failure = None

    @staticmethod
    def _log_url(url):
        """Return useful request context without retaining query values or credentials."""
        parts = urlsplit(url)
        return urlunsplit((parts.scheme, parts.netloc, parts.path, '', ''))

    def _request(self, url, stage=None):
        stage = stage or self.request_stage
        safe_url = self._log_url(url)
        host = urlsplit(url).hostname or 'unknown'
        for attempt in range(3):
            time.sleep(max(0, self.delay - (time.monotonic() - self.last_request)))
            self.last_request = time.monotonic()
            try:
                response = self.session.get(url, timeout=(10, 30), allow_redirects=False)
            except requests.RequestException as exc:
                if attempt == 2:
                    raise
                LOGGER.info(
                    'Retrying stage=%s host=%s url=%s exception=%s attempt=%d/3',
                    stage, host, safe_url, type(exc).__name__, attempt + 1,
                )
                time.sleep(2 ** attempt)
                continue
            if response.status_code not in (500, 502, 503, 504) or attempt == 2:
                return response
            LOGGER.info(
                'Retrying stage=%s host=%s url=%s status=%s attempt=%d/3',
                stage, host, safe_url, response.status_code, attempt + 1,
            )
            time.sleep(2 ** attempt)

    def permitted(self, url):
        parts = urlsplit(url)
        origin = f'{parts.scheme}://{parts.netloc}'
        if origin not in self.robots:
            response = self._request(origin + '/robots.txt', stage='robots')
            robot = RobotFileParser()
            if response.status_code == 404:
                robot.parse(['User-agent: *', 'Allow: /'])
            elif response.status_code == 200 and 'html' not in response.headers.get('Content-Type', '').lower():
                robot.parse(response.text.splitlines())
            else:
                LOGGER.warning('Cannot verify robots policy for %s; skipping', origin)
                robot.parse(['User-agent: *', 'Disallow: /'])
            self.robots[origin] = robot
            crawl_delay = robot.crawl_delay(self.user_agent) or robot.crawl_delay('*')
            if crawl_delay:
                self.delay = max(self.delay, crawl_delay)
        return self.robots[origin].can_fetch(self.user_agent, url)

    def fetch(self, url):
        self.last_failure = None
        try:
            for _ in range(6):
                if (not allowed_url(url, self.hosts)
                        or (self.url_validator is not None and not self.url_validator(url))
                        or not self.permitted(url)):
                    LOGGER.info('Skipped disallowed URL: %s', url)
                    self.last_failure = {'kind': 'policy_denied'}
                    return None
                response = self._request(url)
                if response.status_code in (301, 302, 303, 307, 308):
                    url = urljoin(url, response.headers.get('Location', ''))
                    continue
                response.raise_for_status()
                return response
        except requests.RequestException as exc:
            self.last_failure = {'kind': type(exc).__name__,
                                 'stage': self.request_stage,
                                 'host': urlsplit(url).hostname,
                                 'url': self._log_url(url),
                                 'http_status': exc.response.status_code if exc.response is not None else None}
            LOGGER.warning(
                'Fetch failed stage=%s host=%s url=%s exception=%s',
                self.request_stage, self.last_failure['host'],
                self.last_failure['url'], type(exc).__name__,
            )
        if self.last_failure is None:
            self.last_failure = {'kind': 'redirect_limit'}
        return None


def discover(html, base_url, accepts):
    soup = BeautifulSoup(html, 'lxml')
    return list(dict.fromkeys(
        normalize_url(urljoin(base_url, link['href']))
        for link in soup.select('a[href]')
        if accepts(urljoin(base_url, link['href']))
    ))


def parse_article(html, url, source, hosts, selectors):
    """Use article metadata and publisher body containers; never scrape whole-page text."""
    soup = BeautifulSoup(html, 'lxml')
    documents = []

    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            kinds = value.get('@type', [])
            if isinstance(kinds, str):
                kinds = [kinds]
            if any(kind in ('NewsArticle', 'Article', 'ReportageNewsArticle') for kind in kinds):
                documents.append(value)
            if '@graph' in value:
                walk(value['@graph'])

    for tag in soup.select('script[type="application/ld+json"]'):
        try:
            walk(json.loads(tag.string or tag.get_text()))
        except (ValueError, TypeError):
            continue
    metadata = max(documents, key=lambda item: len(str(item.get('articleBody') or '')), default={})
    if metadata.get('isAccessibleForFree') in (False, 'False', 'false') or soup.select_one('[class*="paywall"], [id*="paywall"]'):
        return None

    def meta(key):
        tag = soup.find('meta', attrs={'property': key}) or soup.find('meta', attrs={'name': key})
        return (tag.get('content') or '').strip() if tag else ''

    body = metadata.get('articleBody')
    if not isinstance(body, str) or not body.strip():
        body = ''
        for selector in selectors:
            node = soup.select_one(selector)
            if node:
                for unwanted in node.select('script, style, aside, nav, form, .related, .advertisement'):
                    unwanted.decompose()
                paragraphs = [p.get_text(' ', strip=True) for p in node.select('p')]
                body = '\n\n'.join(p for p in paragraphs if p)
                if body:
                    break
    title = metadata.get('headline') or meta('og:title')
    if not title and soup.h1:
        title = soup.h1.get_text(' ', strip=True)
    if not title or not body.strip():
        return None
    canonical = soup.select_one('link[rel="canonical"]')
    canonical_url = urljoin(url, canonical.get('href', '')) if canonical else url
    if not allowed_url(canonical_url, hosts):
        return None
    author = metadata.get('author') or meta('author') or ''
    if isinstance(author, list):
        author = ', '.join(str(item.get('name') or '') if isinstance(item, dict) else str(item) for item in author)
    elif isinstance(author, dict):
        author = author.get('name') or ''
    language = metadata.get('inLanguage') or (soup.html.get('lang') if soup.html else '') or ''
    if isinstance(language, dict):
        language = language.get('name') or ''
    text = body.strip()
    return {
        'source': source, 'url': normalize_url(url), 'canonical_url': normalize_url(canonical_url),
        'title': str(title).strip(), 'author': str(author).strip(),
        'published_at': metadata.get('datePublished') or meta('article:published_time'),
        'article_text': text, 'language': language,
        'scraped_at': datetime.now(timezone.utc).isoformat(),
        'content_hash': hashlib.sha256(text.encode('utf-8')).hexdigest(),
        'parser_version': PARSER_VERSION, 'section': metadata.get('articleSection') or '',
        'kenya_relevance': 'needs_review',
        'kenya_relevance_basis': 'Discovered through a Kenyan publisher; geographic relevance is not confirmed.',
    }
