"""Daily Nation reporting from the user-selected Wayback listing."""
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup
from scrapers.common import allowed_url, normalize_url, parse_article
from scrapers.archive import archive_parts as replay_parts, discover_archive

SOURCE = 'nation'
HOSTS = ('web.archive.org',)
PUBLISHER_HOSTS = ('nation.africa', 'www.nation.africa')
CAPTURE = '20240616131714'
LISTINGS = (
    f'https://web.archive.org/web/{CAPTURE}/https://nation.africa/kenya/',
)
# Monthly CDX discovery mirrors the publisher URL scope proven by LISTINGS while
# supplying the requested month separately.
CDX_INDEX_SCOPE = ('nation.africa/kenya/', 'prefix')
FEEDS = ()
BODY_SELECTORS = ('.nation-archive-body',)


def archive_parts(url):
    return replay_parts(url, PUBLISHER_HOSTS)


def is_article(url):
    return allowed_url(url, PUBLISHER_HOSTS) and bool(re.fullmatch(r'/kenya/(?:news|counties|business|sports|life-and-style|health|weekly-review|blogs-opinion)/.+-\d+/?', urlsplit(url).path))


def accepts(url):
    parts = archive_parts(url)
    return bool(parts and is_article(parts[1]))


def accepts_fetch(url):
    """Allow only this publisher's news replay pages, including capture redirects."""
    parts = archive_parts(url)
    return bool(parts and (is_article(parts[1]) or re.fullmatch(
        r'/kenya/?', urlsplit(parts[1]).path
    )))


def discover(html, base_url):
    return discover_archive(html, base_url, PUBLISHER_HOSTS, is_article)


def parse(html, url):
    parts = archive_parts(url)
    if not parts or not is_article(parts[1]):
        return None
    timestamp, original = parts
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
        archive_url=normalize_url(url),
        archive_capture_timestamp=timestamp,
        parser_version='nation-archive-2.0',
        kenya_relevance_basis='Archived Daily Nation reporting; geographic relevance requires review.',
    )
    return article
