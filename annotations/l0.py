"""Pure deterministic extraction/provenance checks; no publisher or GCS requests."""

from datetime import date, datetime
import hashlib
import re
from urllib.parse import urlsplit

from annotations.schemas import AnnotationResult, DEFAULT_CONFIG


SOURCE_DOMAINS = {
    "nation": ("nation.africa", "www.nation.africa"),
    "citizen": ("citizen.digital", "www.citizen.digital"),
    "standard": ("standardmedia.co.ke", "www.standardmedia.co.ke"),
    "star": ("the-star.co.ke", "www.the-star.co.ke"),
    "tuko": ("tuko.co.ke", "www.tuko.co.ke"),
    "kenyans": ("kenyans.co.ke", "www.kenyans.co.ke"),
    "taifaleo": ("taifaleo.nation.co.ke", "www.taifaleo.nation.co.ke"),
}
BLOCK_MARKERS = ("access denied", "verify you are human", "checking your browser", "just a moment")
PAYWALL_MARKERS = ("subscribe to continue reading", "subscribe to read this article", "unlock this article")
BOILERPLATE_MARKERS = ("enable javascript", "accept all cookies", "page not found")


def gcs_reference(value):
    if not isinstance(value, str):
        return False
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == "gs" and bool(re.fullmatch(r"[a-z0-9][a-z0-9._-]{1,220}[a-z0-9]", parsed.netloc))
                and bool(parsed.path.strip("/")) and not parsed.query and not parsed.fragment)
    except ValueError:
        return False


def evaluate_l0(article, config=DEFAULT_CONFIG):
    hard, soft = [], []
    title = article.get("title") if isinstance(article.get("title"), str) else ""
    body = article.get("article_text") if isinstance(article.get("article_text"), str) else ""
    source, canonical = article.get("source"), article.get("canonical_url")
    if not title.strip(): hard.append("missing_title")
    if not body.strip():
        hard.append("missing_body")
    elif len(body.strip()) < config.unusable_body_chars:
        hard.append("unusable_body")
    elif len(body.strip()) < config.minimum_body_chars or len(body.split()) < config.minimum_body_words:
        soft.append("body_too_short")
    if not source:
        hard.append("missing_source")
    elif source not in SOURCE_DOMAINS:
        hard.append("unknown_source")
    if not canonical:
        hard.append("missing_canonical_url")
    else:
        try:
            parsed = urlsplit(canonical)
            hosts = SOURCE_DOMAINS.get(source, ())
            if source == "nation" and article.get("content_scope") == "corporate_news":
                hosts = ("nationmedia.com", "www.nationmedia.com")
                soft.append("non_reporting_scope")
            if (parsed.scheme not in ("https", "http") or parsed.hostname not in hosts
                    or parsed.username or parsed.password or parsed.port not in (None, 80, 443)):
                hard.append("unexpected_domain")
        except (TypeError, ValueError):
            hard.append("unexpected_domain")
    published = article.get("published_at") or article.get("published_at_raw")
    if not published:
        soft.append("missing_published_at")
    else:
        try:
            if isinstance(published, datetime):
                pass
            elif isinstance(published, date):
                pass
            elif isinstance(published, str):
                datetime.fromisoformat(published.replace("Z", "+00:00"))
            else:
                raise ValueError
        except ValueError:
            soft.append("invalid_published_at")
    for field, code in (("raw_object_uri", "missing_raw_uri"), ("processed_object_uri", "missing_processed_uri")):
        if not gcs_reference(article.get(field)):
            hard.append(code)
    content_hash = article.get("content_hash")
    if not content_hash:
        hard.append("missing_content_hash")
    elif not isinstance(content_hash, str) or not re.fullmatch(r"[a-fA-F0-9]{64}", content_hash):
        hard.append("invalid_content_hash")
    elif body and hashlib.sha256(body.encode("utf-8")).hexdigest() != content_hash.lower():
        hard.append("content_hash_mismatch")
    if not article.get("parser_version"):
        hard.append("missing_parser_version")
    if article.get("processed_object_missing"):
        hard.append("missing_processed_object")
    hard.extend(article.get("lineage_errors", []))
    prefix = f"{title}\n{body[:500]}".casefold()
    if any(marker in prefix for marker in BLOCK_MARKERS): hard.append("suspected_block_page")
    if any(marker in body.casefold() for marker in PAYWALL_MARKERS): soft.append("suspected_paywall")
    if any(marker in prefix for marker in BOILERPLATE_MARKERS): soft.append("suspected_boilerplate")
    if body.rstrip().endswith(("...", "…", "[read more]")): soft.append("suspected_truncation")
    if re.search(r"<(?:html|body|script|div|p)[\s>]", body, re.I): soft.append("suspected_html_body")
    hard, soft = sorted(set(hard)), sorted(set(soft))
    return AnnotationResult("L0", "invalid" if hard else "needs_review" if soft else "valid",
                            "extraction_quality_rules", config.method_version("L0"),
                            evidence={"body_chars": len(body.strip()), "body_words": len(body.split()),
                                      "hard_failures": hard, "soft_anomalies": soft,
                                      "publication_date_flagged": bool(article.get("publication_date_needs_review")),
                                      "minimum_body_chars": config.minimum_body_chars,
                                      "minimum_body_words": config.minimum_body_words},
                            reason_codes=hard + soft)
