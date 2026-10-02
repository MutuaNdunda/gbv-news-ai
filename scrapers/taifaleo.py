"""Taifa Leo article parsing and bounded discovery from the supplied CDX query."""
from datetime import datetime
import re
from urllib.parse import parse_qs, urljoin, urlsplit

from bs4 import BeautifulSoup

from scrapers.archive import archive_parts as replay_parts, discover_archive
from scrapers.common import allowed_url, normalize_url, parse_article

SOURCE = "taifaleo"
HOSTS = ("web.archive.org",)
PUBLISHER_HOSTS = ("taifaleo.nation.co.ke", "www.taifaleo.nation.co.ke")
CDX_URL = (
    "https://web.archive.org/cdx/search/cdx?url=taifaleo.nation.co.ke/*"
    "&output=json&fl=timestamp,original,statuscode,mimetype"
    "&filter=statuscode:200&filter=mimetype:text/html&collapse=urlkey&limit=500"
)
LISTINGS = ()
FEEDS = ()
BODY_SELECTORS = (".news-details-layout1", ".article-content__content", ".entry-content", "[itemprop='articleBody']")
NON_ARTICLE_ROUTES = {
    "author", "category", "tag", "page", "feed", "wp-admin", "wp-content",
    "wp-includes", "wp-json", "search", "sitemap", "about", "about-us",
    "contact", "contact-us", "privacy-policy", "terms-and-conditions",
}


def archive_parts(url):
    return replay_parts(url, PUBLISHER_HOSTS)


def is_article(url):
    """Accept inspected WordPress slugs and dated stories, excluding navigation."""
    if not allowed_url(url, PUBLISHER_HOSTS):
        return False
    parsed = urlsplit(url)
    if parsed.query:
        return False
    segments = parsed.path.strip("/").split("/")
    if any(part in NON_ARTICLE_ROUTES for part in segments):
        return False
    if len(segments) == 4:
        try:
            datetime.strptime("/".join(segments[:3]), "%Y/%m/%d")
        except ValueError:
            return False
    elif len(segments) != 1:
        return False
    return bool(re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)+", segments[-1]))


def accepts(url):
    parts = archive_parts(url)
    return bool(parts and is_article(parts[1]))


def accepts_fetch(url):
    if allowed_url(url, HOSTS) and urlsplit(url).path == "/cdx/search/cdx":
        return parse_qs(urlsplit(url).query).get("url") == ["taifaleo.nation.co.ke/*"]
    parts = archive_parts(url)
    return bool(parts and (is_article(parts[1]) or urlsplit(parts[1]).path == "/"))


def discover(html, base_url):
    return discover_archive(html, base_url, PUBLISHER_HOSTS, is_article)


def cdx_records(payload):
    """Validate the four-column CDX response before treating any row as a capture."""
    if not isinstance(payload, list):
        raise ValueError("Expected Taifa Leo CDX JSON array")
    if not payload:
        return []
    if payload[0] != ["timestamp", "original", "statuscode", "mimetype"]:
        raise ValueError("Unexpected Taifa Leo CDX columns")
    records = []
    for row in payload[1:]:
        if (not isinstance(row, list) or len(row) != 4
                or not all(isinstance(item, str) for item in row)
                or not re.fullmatch(r"\d{14}", row[0])):
            raise ValueError("Invalid Taifa Leo CDX record")
        timestamp, original, status, mime = row
        if status == "200" and mime == "text/html" and is_article(original):
            records.append((timestamp, normalize_url(original)))
    return records


def expanded_candidates(client, max_pages=1):
    """Use one bounded all-date CDX batch; the supplied query has no continuation."""
    response = client.fetch(CDX_URL, stage="CDX_INDEX")
    if response is None:
        raise RuntimeError("Taifa Leo CDX discovery failed; archive coverage is unknown")
    seen = set()
    for timestamp, original in cdx_records(response.json()):
        if original not in seen:
            seen.add(original)
            yield f"https://web.archive.org/web/{timestamp}id_/{original}", CDX_URL, "wayback_cdx"


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
    body = soup.select_one(".news-details-layout1")
    visible_date = visible_author = ""
    modern_body = soup.select_one(".article-content__content")
    if modern_body:
        for unwanted in modern_body.select(".incontent-ad, [class^='mobile-ad'], .content-capt, figure"):
            unwanted.decompose()
        date_meta = soup.find("meta", attrs={"property": "og:article:published_time"})
        if date_meta:
            visible_date = (date_meta.get("content") or "").strip()
        author_node = soup.select_one(".meta-author")
        if author_node:
            visible_author = re.sub(r"^(?:NA|BY)\s+", "", author_node.get_text(" ", strip=True), flags=re.I)
    if body:
        headline = body.select_one("h2.title-semibold-dark")
        if headline:
            if soup.h1 and not soup.h1.get_text(strip=True):
                soup.h1.decompose()
            if soup.h1 is None:
                headline.name = "h1"
        date_icon = body.select_one(".post-info-dark .fa-calendar")
        if date_icon:
            visible_date = date_icon.parent.get_text(" ", strip=True)
        byline = body.find("p")
        if byline and re.match(r"^NA\s+", byline.get_text(" ", strip=True), re.I):
            visible_author = re.sub(r"^NA\s+", "", byline.get_text(" ", strip=True), flags=re.I)
            byline.decompose()
        for unwanted in body.select(".post-info-dark, .related, .related-posts, figure"):
            unwanted.decompose()
    article = parse_article(str(soup), original, SOURCE, PUBLISHER_HOSTS, BODY_SELECTORS)
    if not article:
        return None
    if visible_author:
        article["author"] = visible_author
    raw_date = article["published_at"] or visible_date
    if raw_date:
        article["published_at_raw"] = raw_date
        try:
            try:
                published = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            except ValueError:
                published = datetime.strptime(raw_date, "%B %d, %Y")
            article["published_at"] = published.isoformat()
            if published.tzinfo is None:
                article["publication_timezone"] = "unknown"
                if published.time() == datetime.min.time() and visible_date == raw_date:
                    article["publication_date_precision"] = "day"
        except (TypeError, ValueError):
            article["published_at"] = None
            article["publication_date_needs_review"] = True
    # The inspected legacy template says en-US despite its Swahili prose. Keep
    # that evidence without treating the template language as a verified label.
    if article["language"] == "en-US":
        article["language_metadata_raw"] = article["language"]
        article["language"] = ""
        article["language_needs_review"] = True
    article.update(
        publisher_name="Taifa Leo", publisher_domain=urlsplit(original).hostname,
        content_scope="news_reporting", archive_url=normalize_url(url),
        archive_capture_timestamp=timestamp, parser_version="taifaleo-archive-1.1",
        kenya_relevance_basis="Archived Taifa Leo reporting; geographic relevance requires review.",
    )
    return article
