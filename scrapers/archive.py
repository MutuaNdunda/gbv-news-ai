"""Restricted Wayback replay discovery shared by archived publishers."""
import re
from urllib.parse import urljoin, urlsplit
from bs4 import BeautifulSoup
from scrapers.common import allowed_url, normalize_url


def archive_parts(url, publisher_hosts):
    """Validate a dated HTML replay and its embedded publisher URL."""
    if not allowed_url(url, ('web.archive.org',)):
        return None
    match = re.fullmatch(r'/web/(\d{14})/(https?://.+)', urlsplit(url).path)
    if not match:
        return None
    timestamp, original = match.groups()
    if urlsplit(url).query:
        original += '?' + urlsplit(url).query
    if not allowed_url(original, publisher_hosts):
        return None
    return timestamp, normalize_url(original)


def discover_archive(html, base_url, publisher_hosts, is_article):
    parts = archive_parts(base_url, publisher_hosts)
    if not parts:
        return []
    timestamp, original_base = parts
    soup = BeautifulSoup(html, 'lxml')
    results = []
    seen = set()
    for link in soup.select('a[href]'):
        # Premium labels on the listing apply to the linked story.
        if link.select_one('.premium') or link.get_text(' ', strip=True).startswith('PREMIUM'):
            continue
        href = link['href']
        replay = urljoin(base_url, href)
        archived = archive_parts(replay, publisher_hosts)
        if archived:
            original = archived[1]
        else:
            original = urljoin(original_base, href)
            replay = f'https://web.archive.org/web/{timestamp}/{original}'
        if is_article(original) and archive_parts(replay, publisher_hosts) and original not in seen:
            seen.add(original)
            results.append(normalize_url(replay))
    return results
