"""Daily Nation reporting from the user-selected Wayback listing."""
import re
import logging
from collections import deque
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup
from scrapers.common import allowed_url, normalize_url, parse_article
from scrapers.archive import archive_parts as replay_parts, discover_archive

SOURCE = 'nation'
HOSTS = ('web.archive.org',)
PUBLISHER_HOSTS = ('nation.africa', 'www.nation.africa')
ARCHIVE_PREFIXES = ('https://nation.africa/kenya/', 'https://www.nation.africa/kenya/')
LIVE_LISTINGS = ('https://nation.africa/kenya/',)
CAPTURE = '20240616131714'
LISTINGS = (
    f'https://web.archive.org/web/{CAPTURE}/https://nation.africa/kenya/',
)
FEEDS = ()
BODY_SELECTORS = ('.nation-archive-body',)


def archive_parts(url):
    return replay_parts(url, PUBLISHER_HOSTS)


def is_article(url):
    return allowed_url(url, PUBLISHER_HOSTS) and bool(re.fullmatch(r'/kenya/(?:news|counties|business|sports|life-and-style|health|weekly-review|blogs-opinion)/.+-\d+/?', urlsplit(url).path))


def accepts(url):
    parts = archive_parts(url)
    return bool(parts and is_article(parts[1]))


def is_listing(url):
    """Restrict discovery to Kenya sections and ordinary page pagination."""
    if not allowed_url(url, PUBLISHER_HOSTS):
        return False
    parts = urlsplit(url)
    query = parse_qs(parts.query, keep_blank_values=True)
    return (bool(re.fullmatch(
        r'/kenya(?:/(?:news|counties|business|sports|life-and-style|health|weekly-review|blogs-opinion)(?:/[a-z][a-z-]*)?)?/?',
        parts.path))
        and (not query or (set(query) == {'page'} and len(query['page']) == 1
                           and query['page'][0].isdigit() and int(query['page'][0]) > 0)))


def accepts_fetch(url):
    """Allow only this publisher's news replay pages, including capture redirects."""
    parts = archive_parts(url)
    return bool(parts and (is_article(parts[1]) or is_listing(parts[1])))


def discover(html, base_url):
    return discover_archive(html, base_url, PUBLISHER_HOSTS, is_article)


def expanded_candidates(client, max_pages=1):
    """Follow linked archived sections/pages within a bounded request budget."""
    if max_pages < 1:
        raise ValueError('Nation max_pages must be positive')
    queue = deque(LISTINGS)
    visited, seen_articles = set(), set()
    attempted = 0
    while queue and attempted < max_pages:
        listing = queue.popleft()
        original = archive_parts(listing)[1]
        if original in visited:
            continue
        visited.add(original)
        attempted += 1
        response = client.fetch(listing, stage='LISTING')
        if response is None:
            raise RuntimeError('Nation archive listing failed; discovery coverage is unknown')
        actual = archive_parts(response.url)
        if not actual or not is_listing(actual[1]):
            raise ValueError('Unexpected Nation archive listing redirect')
        visited.add(actual[1])
        articles = discover(response.content, response.url)
        logging.getLogger(__name__).info('Nation listing %d/%d: %d article links',
                                         attempted, max_pages, len(articles))
        sections = discover_archive(response.content, response.url, PUBLISHER_HOSTS, is_listing)
        queue.extend(sections)
        for article in articles:
            identity = archive_parts(article)[1]
            if identity not in seen_articles:
                seen_articles.add(identity)
                yield article, response.url, 'archive_listing'
    if any(archive_parts(url)[1] not in visited for url in queue):
        logging.getLogger(__name__).warning('Nation listing page limit reached; linked pages remain')


def parse(html, url):
    return _parse(html, url, live=False)


def parse_live(html, url):
    """Parse a public live article without inventing archive provenance."""
    return _parse(html, url, live=True)


def _parse(html, url, live=False):
    parts = archive_parts(url)
    if live:
        if not is_article(url):
            return None
        timestamp, original = None, url
    elif parts and is_article(parts[1]):
        timestamp, original = parts
    else:
        return None
    soup = BeautifulSoup(html, 'lxml')
    # Wayback rewrites canonical links; normalize them back to publisher URLs.
    for canonical in soup.select('link[rel="canonical"]'):
        href = urljoin(url, canonical.get('href', ''))
        archived = archive_parts(href)
        canonical['href'] = archived[1] if archived else urljoin(original, canonical.get('href', ''))
        if not is_article(canonical['href']):
            return None
    if soup.select_one('.article-header .premium'):
        return None
    # Nation includes this inactive template on accessible articles too. Its
    # hidden state is explicit in the source; active paywalls remain rejected.
    for template in soup.select('#paywall.hidden, #paywall[hidden]'):
        template.decompose()
    body = soup.new_tag('div', attrs={'class': 'nation-archive-body'})
    for wrapper in soup.select('.article-content .paragraph-wrapper'):
        for paragraph in list(wrapper.select('p')):
            body.append(paragraph.extract())
    soup.append(body)
    article = parse_article(str(soup), original, SOURCE, PUBLISHER_HOSTS, BODY_SELECTORS)
    if not article:
        return None
    article.update(
        publisher_name='Daily Nation',
        publisher_domain=urlsplit(original).hostname,
        content_scope='news_reporting',
        parser_version='nation-archive-2.0',
        kenya_relevance_basis=('Daily Nation reporting; geographic relevance requires review.' if live
                               else 'Archived Daily Nation reporting; geographic relevance requires review.'),
    )
    if not live:
        article.update(archive_url=normalize_url(url), archive_capture_timestamp=timestamp)
    else:
        article['parser_version'] = 'nation-live-1.0'
    return article
