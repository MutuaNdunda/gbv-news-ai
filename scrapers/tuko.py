"""Tuko reporting from the user-selected archived homepage."""
from datetime import datetime
import re
from urllib.parse import urljoin, urlsplit

from bs4 import BeautifulSoup

from scrapers.archive import archive_parts as replay_parts, discover_archive
from scrapers.common import allowed_url, normalize_url, parse_article

SOURCE = "tuko"
HOSTS = ("web.archive.org",)
PUBLISHER_HOSTS = ("tuko.co.ke", "www.tuko.co.ke")
CAPTURE = "20260831023500"
LISTINGS = (f"https://web.archive.org/web/{CAPTURE}/https://www.tuko.co.ke/",)
FEEDS = ()
BODY_SELECTORS = (".post__content",)


def archive_parts(url):
    return replay_parts(url, PUBLISHER_HOSTS)


def is_article(url):
    """Accept section stories containing Tuko's numeric article identifier."""
    return allowed_url(url, PUBLISHER_HOSTS) and bool(re.fullmatch(
        r"/(?:[a-z0-9-]+/){1,3}\d{5,}-[^/]+/?", urlsplit(url).path,
    ))


def accepts(url):
    parts = archive_parts(url)
    return bool(parts and is_article(parts[1]))


def accepts_fetch(url):
    parts = archive_parts(url)
    return bool(parts and (is_article(parts[1]) or urlsplit(parts[1]).path == "/"))


def discover(html, base_url):
    return discover_archive(html, base_url, PUBLISHER_HOSTS, is_article)


def parse(html, url):
    parts = archive_parts(url)
    if not parts or not is_article(parts[1]):
        return None
    timestamp, original = parts
    soup = BeautifulSoup(html, "lxml")
    for canonical in soup.select('link[rel="canonical"]'):
        href = urljoin(url, canonical.get("href", ""))
        archived = archive_parts(href)
        canonical["href"] = archived[1] if archived else urljoin(original, canonical.get("href", ""))
        if not is_article(canonical["href"]):
            return None
    if soup.select_one(".post__header .premium, .post__header [class*='premium']"):
        return None
    for unwanted in soup.select(
        ".post__content .post__read-also, .post__content .call_to_action, "
        ".post__content figure, .post__content .c-adv"
    ):
        unwanted.decompose()
    article = parse_article(str(soup), original, SOURCE, PUBLISHER_HOSTS, BODY_SELECTORS)
    if not article:
        return None
    if article["published_at"]:
        raw_date = article["published_at"]
        try:
            published = datetime.fromisoformat(raw_date)
            article["published_at_raw"] = raw_date
            article["published_at"] = published.isoformat()
            if published.tzinfo is None:
                article["publication_timezone"] = "unknown"
        except (TypeError, ValueError):
            article["publication_date_needs_review"] = True
    article.update(
        publisher_name="Tuko.co.ke", publisher_domain=urlsplit(original).hostname,
        content_scope="news_reporting", archive_url=normalize_url(url),
        archive_capture_timestamp=timestamp, parser_version="tuko-archive-1.0",
        kenya_relevance_basis="Archived Tuko reporting; geographic relevance requires review.",
    )
    return article
