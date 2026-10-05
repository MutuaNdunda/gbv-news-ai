"""Signed-session CSRF and explicitly local, configured reviewer access."""
import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit

from flask import abort, current_app, request, session


def csrf_token(key):
    return session.setdefault(key, secrets.token_urlsafe(32))


def require_csrf(key):
    expected = session.get(key, "")
    supplied = request.form.get("csrf_token", "")
    if not expected or not hmac.compare_digest(expected.encode(), supplied.encode()):
        abort(403)


def local_review_request():
    """No reverse-proxy/remote review until proper reviewer authentication exists."""
    return (request.remote_addr in ("127.0.0.1", "::1")
            and urlsplit(request.host_url).hostname in ("localhost", "127.0.0.1", "::1")
            and not request.headers.get("Forwarded")
            and not request.headers.get("X-Forwarded-For"))


def review_enabled():
    config = current_app.config
    return (config.get("HUMAN_REVIEW_ENABLED", False)
            and len(config.get("HUMAN_REVIEW_TOKEN") or "") >= 32
            and len(current_app.secret_key or "") >= 32
            and bool((config.get("HUMAN_REVIEWER_ID") or "").strip())
            and bool((config.get("HUMAN_REVIEW_GUIDELINE_VERSION") or "").strip()))


def review_binding():
    parts = [current_app.config.get(name, "") for name in
             ("HUMAN_REVIEW_TOKEN", "HUMAN_REVIEWER_ID", "HUMAN_REVIEW_GUIDELINE_VERSION")]
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def review_authenticated():
    elapsed = time.time() - session.get("human_review_started", 0)
    return (review_enabled() and local_review_request() and 0 <= elapsed < 1800
            and hmac.compare_digest(session.get("human_review_binding", ""), review_binding()))


def unlock_review(token):
    if not review_enabled() or not local_review_request():
        abort(403)
    if not hmac.compare_digest(token.encode(), current_app.config["HUMAN_REVIEW_TOKEN"].encode()):
        abort(403)
    session["human_review_binding"] = review_binding()
    session["human_review_started"] = time.time()
