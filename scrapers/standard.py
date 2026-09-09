"""The Standard reporting from the user-selected archived homepage."""
from datetime import datetime, timedelta, timezone
from collections import deque
from itertools import zip_longest
import logging
import re
from urllib.parse import urljoin, urlsplit, parse_qs

from bs4 import BeautifulSoup
from scrapers.archive import archive_parts as replay_parts, discover_archive
from scrapers.common import allowed_url, normalize_url, parse_article

SOURCE = 'standard'
HOSTS = ('web.archive.org',)
PUBLISHER_HOSTS = ('standardmedia.co.ke', 'www.standardmedia.co.ke')
CAPTURE = '20200812220501'
LISTINGS = (f'https://web.archive.org/web/{CAPTURE}/https://standardmedia.co.ke/',)
FEEDS = ()
BODY_SELECTORS = ('.standard-archive-body', '.article-body', '.story-content', '[itemprop="articleBody"]')


def archive_parts(url):
    return replay_parts(url, PUBLISHER_HOSTS)


def is_article(url):
    return allowed_url(url, PUBLISHER_HOSTS) and bool(re.fullmatch(
        r'/(?:[^/]+/)?article/\d+/[^/]+/?', urlsplit(url).path,
    ))


def is_listing(url):
    if not allowed_url(url, PUBLISHER_HOSTS):
        return False
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    return (bool(re.fullmatch(r'/(?:business/|sports/)?category/\d+/[^/]+/?', parts.path))
            and (not query or (set(query) == {'page'} and len(query['page']) == 1
                               and query['page'][0].isdigit() and int(query['page'][0]) > 0)))



def accepts(url):
    parts = archive_parts(url)
    return bool(parts and is_article(parts[1]))


def accepts_fetch(url):
    parts = archive_parts(url)
    return bool(parts and (is_article(parts[1]) or is_listing(parts[1]) or urlsplit(parts[1]).path == '/'))


def discover(html, base_url):
    return discover_archive(html, base_url, PUBLISHER_HOSTS, is_article)


def expanded_candidates(client, max_pages):
    """Fetch a bounded breadth-first set of listings, then interleave their articles."""
    queue = deque(LISTINGS)
    visited = set()
    pages = []
    attempted = 0
    while queue and attempted < max_pages:
        listing = queue.popleft()
        parts = archive_parts(listing)
        if not parts or parts[1] in visited:
            continue
        visited.add(parts[1])
        attempted += 1
        response = client.fetch(listing)
        if response is None:
            continue
        actual = archive_parts(response.url)
        if not actual or not (is_listing(actual[1]) or urlsplit(actual[1]).path == '/'):
            continue
        visited.add(actual[1])
        articles = discover(response.content, response.url)
        pages.append([(url, response.url, 'archive_listing') for url in articles])
        logging.getLogger(__name__).info('Listing %d/%d: %d article links from %s',
                                        attempted, max_pages, len(articles), response.url)
        sections = discover_archive(response.content, response.url, PUBLISHER_HOSTS, is_listing)
        # Deterministic ordering puts domestic reporting sections first.
        sections.sort(key=lambda url: (not any(term in url for term in
                      ('/national', '/education', '/politics', '/nairobi')), url))
        queue.extend(sections)
    seen = set()
    for row in zip_longest(*pages):
        for candidate in row:
            if candidate is None:
                continue
            original = archive_parts(candidate[0])[1]
            if original not in seen:
                seen.add(original)
                yield candidate


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
    content = soup.select_one('.standard-content .content')
    if content:
        # This 2020 layout stores prose as direct text nodes between related
        # links, rather than consistently wrapping each paragraph in <p>.
        for unwanted in content.select('script, style, figure, aside, nav, form, .seealso, .list-group, .row, .advertisement'):
            unwanted.decompose()
        body = soup.new_tag('div', attrs={'class': 'standard-archive-body'})
        paragraph = soup.new_tag('p')
        paragraph.string = content.get_text('\n', strip=True)
        body.append(paragraph)
        soup.append(body)
    article = parse_article(str(soup), original, SOURCE, PUBLISHER_HOSTS, BODY_SELECTORS)
    if not article:
        return None
    raw_date = article['published_at']
    if raw_date:
        article['published_at_raw'] = raw_date
        try:
            published = datetime.strptime(raw_date.strip(), '%a, %d %b %Y %H:%M:%S EAT')
            article['published_at'] = published.replace(tzinfo=timezone(timedelta(hours=3))).isoformat()
        except (ValueError, TypeError):
            try:
                published = datetime.fromisoformat(raw_date.replace('Z', '+00:00'))
                article['published_at'] = published.isoformat()
                if published.tzinfo is None:
                    article['publication_timezone'] = 'unknown'
            except (ValueError, TypeError):
                article['publication_date_needs_review'] = True
    article.update(
        publisher_name='The Standard', publisher_domain=urlsplit(original).hostname,
        content_scope='news_reporting', archive_url=normalize_url(url),
        archive_capture_timestamp=timestamp, parser_version='standard-archive-1.1',
        kenya_relevance_basis='Archived Standard reporting; geographic relevance requires review.',
    )
    return article
