"""The Star reporting from the user-selected archived homepage."""
from datetime import datetime
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from scrapers.archive import archive_parts as replay_parts, discover_archive
from scrapers.common import allowed_url, normalize_url, parse_article

SOURCE = 'star'
HOSTS = ('web.archive.org',)
PUBLISHER_HOSTS = ('the-star.co.ke', 'www.the-star.co.ke')
CAPTURE = '20251227053140'
LISTINGS = (f'https://web.archive.org/web/{CAPTURE}/https://www.the-star.co.ke/',)
CDX_INDEX_SCOPE = ('www.the-star.co.ke/', 'prefix')
FEEDS = ()
BODY_SELECTORS = ('.story-content',)


def archive_parts(url):
    return replay_parts(url, PUBLISHER_HOSTS)


def is_article(url):
    return allowed_url(url, PUBLISHER_HOSTS) and bool(re.fullmatch(
        r'/(?:news|counties|business|sports|health|sasa|siasa|opinion|climate-change)/(?:[^/]+/)*\d{4}-\d{2}-\d{2}-[^/]+/?',
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
    if soup.select_one('.story-header .premium'):
        return None
    article = parse_article(str(soup), original, SOURCE, PUBLISHER_HOSTS, BODY_SELECTORS)
    if not article:
        return None
    # The inspected snapshot supplies a visible date but no publication meta tag.
    # Preserve its timezone uncertainty instead of borrowing the archive's UTC time.
    if not article['published_at']:
        for date in soup.select('small.text-wrap.text-center'):
            raw_date = date.get_text(' ', strip=True)
            try:
                published = datetime.strptime(raw_date, '%d %B %Y - %H:%M')
            except ValueError:
                continue
            article.update(published_at=published.isoformat(timespec='minutes'),
                           published_at_raw=raw_date, publication_timezone='unknown')
            break
    article.update(
        publisher_name='The Star Kenya', publisher_domain=urlsplit(original).hostname,
        content_scope='news_reporting', archive_url=normalize_url(url),
        archive_capture_timestamp=timestamp, parser_version='star-archive-1.0',
        kenya_relevance_basis='Archived Star reporting; geographic relevance requires review.',
    )
    return article
