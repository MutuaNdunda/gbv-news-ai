"""Citizen Digital reporting from the user-selected archived homepage."""
from datetime import datetime
from html import unescape
import json
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from scrapers.archive import archive_parts as replay_parts, discover_archive
from scrapers.common import allowed_url, normalize_url, parse_article

SOURCE = 'citizen'
HOSTS = ('web.archive.org',)
PUBLISHER_HOSTS = ('citizen.digital', 'www.citizen.digital')
CAPTURE = '20260304002240'
LISTINGS = (f'https://web.archive.org/web/{CAPTURE}/https://citizen.digital/',)
FEEDS = ()
BODY_SELECTORS = ('.js-article-body', '.article-content-wrapper .the-content')


def archive_parts(url):
    return replay_parts(url, PUBLISHER_HOSTS)


def is_article(url):
    return allowed_url(url, PUBLISHER_HOSTS) and bool(re.fullmatch(
        r'/(?:article|news|business|sports|entertainment|lifestyle|opinion|wananchi|health)/[^/]+-n\d+/?',
        urlsplit(url).path,
    ))



def accepts(url):
    parts = archive_parts(url)
    return bool(parts and is_article(parts[1]))


def accepts_fetch(url):
    parts = archive_parts(url)
    return bool(parts and (is_article(parts[1]) or urlsplit(parts[1]).path == '/'))


def discover(html, base_url):
    return discover_archive(html, base_url, PUBLISHER_HOSTS, is_article)


def parse(html, url):
    parts = archive_parts(url)
    if not parts or not is_article(parts[1]):
        return None
    timestamp, original = parts
    soup = BeautifulSoup(html, 'lxml')
    for canonical in soup.select('link[rel="canonical"]'):
        href = urljoin(url, canonical.get('href', ''))
        archived = archive_parts(href)
        canonical['href'] = archived[1] if archived else urljoin(original, canonical.get('href', ''))
        if not is_article(canonical['href']):
            return None
    # The inspected Citizen snapshot HTML-escapes its JSON-LD script and nests
    # an author object inside author.name. Normalize only this metadata block.
    for tag in soup.select('script[type="application/ld+json"]'):
        raw = tag.string or tag.get_text()
        try:
            try:
                value = json.loads(raw)
            except ValueError:
                value = json.loads(unescape(raw))
        except (ValueError, TypeError):
            continue
        def normalize_author(item):
            if isinstance(item, list):
                for child in item:
                    normalize_author(child)
            elif isinstance(item, dict):
                author = item.get('author')
                if isinstance(author, dict) and isinstance(author.get('name'), dict):
                    author['name'] = author['name'].get('name') or ''
                if '@graph' in item:
                    normalize_author(item['@graph'])
        normalize_author(value)
        tag.string = json.dumps(value)
    article = parse_article(str(soup), original, SOURCE, PUBLISHER_HOSTS, BODY_SELECTORS)
    if not article:
        return None
    if article['published_at']:
        raw_date = article['published_at']
        try:
            published = datetime.fromisoformat(raw_date)
            article['published_at_raw'] = raw_date
            article['published_at'] = published.isoformat()
            if published.tzinfo is None:
                article['publication_timezone'] = 'unknown'
        except (ValueError, TypeError):
            article['publication_date_needs_review'] = True
    article.update(
        publisher_name='Citizen Digital', publisher_domain=urlsplit(original).hostname,
        content_scope='news_reporting', archive_url=normalize_url(url),
        archive_capture_timestamp=timestamp, parser_version='citizen-archive-1.1',
        kenya_relevance_basis='Archived Citizen Digital reporting; geographic relevance requires review.',
    )
    return article
