"""Annotation monitor and opt-in, token/CSRF-protected bounded execution."""

import hmac
import secrets

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for


blueprint = Blueprint("annotations", __name__, url_prefix="/annotations")


def service():
    value = current_app.extensions["monitor_services"].get("annotations")
    if value is None: abort(503)
    return value


def execution_enabled():
    return (current_app.config["ANNOTATION_UI_ENABLED"]
            and len(current_app.config.get("ANNOTATION_UI_TOKEN") or "") >= 32
            and len(current_app.secret_key or "") >= 32)


@blueprint.get("")
def index():
    enabled = execution_enabled()
    csrf = None
    if enabled:
        csrf = session.setdefault("annotation_csrf", secrets.token_urlsafe(32))
    return render_template("annotations/index.html", **service().overview(), execution_enabled=enabled, csrf=csrf)


@blueprint.get("/runs")
def runs():
    page = max(request.args.get("page", 1, type=int), 1)
    rows, total = service().runs(page, current_app.config["PER_PAGE"])
    return render_template("annotations/runs.html", rows=rows, total=total, page=page)


@blueprint.get("/runs/<uuid:run_id>")
def run_detail(run_id):
    data = service().run_detail(run_id)
    if data is None: abort(404)
    return render_template("annotations/run_detail.html", **data)


@blueprint.get("/<layer>")
def results(layer):
    if layer not in ("l0", "l1"): abort(404)
    page = max(request.args.get("page", 1, type=int), 1)
    filters = {key: request.args.get(key, "").strip() for key in ("label", "source")}
    rows, total = service().results(layer.upper(), filters, page, current_app.config["PER_PAGE"])
    return render_template("annotations/results.html", layer=layer.upper(), filters=filters,
                           rows=rows, total=total, page=page)


@blueprint.post("/run")
def run():
    if not execution_enabled(): abort(403)
    if not request.is_secure and request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)
    supplied = request.form.get("execution_token", "")
    if not hmac.compare_digest(supplied.encode(), current_app.config["ANNOTATION_UI_TOKEN"].encode()): abort(403)
    csrf = session.get("annotation_csrf", "")
    if not csrf or not hmac.compare_digest(csrf.encode(), request.form.get("csrf_token", "").encode()): abort(403)
    layers = request.form.get("layers", "")
    limit = request.form.get("limit", type=int)
    if layers not in ("l0", "l1", "l0,l1") or limit is None or not 1 <= limit <= 20:
        abort(400)
    # Rotate the browser session's form token after a successful validation.
    session.pop("annotation_csrf", None)
    try:
        summary = service().run(layers.split(","), limit)
    except Exception as exc:
        current_app.logger.warning("annotation_ui_run_failed error_type=%s", type(exc).__name__)
        flash("Annotation run failed. Check infrastructure and annotation run logs.", "warning")
        return redirect(url_for("annotations.index"), code=303)
    return redirect(url_for("annotations.run_detail", run_id=summary["run_id"]), code=303)
