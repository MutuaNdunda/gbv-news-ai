"""Annotation monitor and opt-in, token/CSRF-protected bounded execution."""

import hmac

from sqlalchemy.exc import SQLAlchemyError

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for


from annotations.schemas import DEFAULT_CONFIG
from annotations.validation import DECISIONS, ERROR_CATEGORIES, LABELS, REVIEW_FILTERS, ReviewConflict, STATUSES
from app.security import (csrf_token, require_csrf, review_authenticated, review_enabled,
                          local_review_request, unlock_review)


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
        csrf = csrf_token("annotation_csrf")
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


def result_filters(layer):
    filters = {key: request.args.get(key, "").strip() for key in ("label", "source", "review_status")}
    labels = LABELS[layer]
    if filters["label"] and filters["label"] not in labels:
        abort(400)
    if filters["source"] and filters["source"] not in ("nation", "citizen", "standard", "star", "tuko", "kenyans", "taifaleo"):
        abort(400)
    if filters["review_status"] and filters["review_status"] not in REVIEW_FILTERS:
        abort(400)
    if layer == "L2":
        filters.update({key: request.args.get(key, "").strip() for key in
                        ("mode", "method_version", "model_version", "pending")})
        if filters["mode"] not in ("", "model", "weak") or filters["pending"] not in ("", "1"):
            abort(400)
        if filters["pending"] and (filters["label"] or filters["method_version"] or filters["model_version"] or filters["review_status"]):
            abort(400)
    return filters


@blueprint.get("/<layer>")
def results(layer):
    if layer not in ("l0", "l1", "l2"): abort(404)
    page = max(request.args.get("page", 1, type=int), 1)
    filters = result_filters(layer.upper())
    try:
        if layer == "l2" and filters.get("pending"):
            rows, total = service().pending_l2(filters, page, current_app.config["PER_PAGE"])
        else:
            rows, total = service().results(layer.upper(), filters, page, current_app.config["PER_PAGE"])
    except RuntimeError:
        abort(503)
    if layer == "l2":
        label_counts = (service().l2_label_counts(filters)
                        if filters.get("mode") == "weak" and not filters.get("pending") else None)
        return render_template("annotations/l2_results.html", rows=rows, total=total, filters=filters,
                               page=page, per_page=current_app.config["PER_PAGE"], label_counts=label_counts,
                               review_statuses=service().review_statuses(rows) if not filters.get("pending") else {},
                               status_labels=STATUSES, review_filter_options=REVIEW_FILTERS)
    statuses = service().review_statuses(rows) if hasattr(service(), "review_statuses") else {}
    return render_template("annotations/results.html", layer=layer.upper(), filters=filters,
                           rows=rows, total=total, page=page, review_statuses=statuses, status_labels=STATUSES,
                           review_filter_options=REVIEW_FILTERS, label_options=LABELS[layer.upper()], per_page=current_app.config["PER_PAGE"],
                           method_version=DEFAULT_CONFIG.method_version(layer.upper()))


@blueprint.get("/l2/<uuid:annotation_id>")
def l2_detail(annotation_id):
    data = service().l2_detail(annotation_id)
    if data is None:
        abort(404)
    filters = result_filters("L2")
    filters["mode"] = filters["mode"] or ("weak" if data["annotation"].method_name == "gbv_relevance_weak_supervision" else "model")
    response = redirect(url_for("annotations.review", annotation_id=annotation_id,
        **dict(filters, page=max(request.args.get("page", 1, type=int), 1))), code=302)
    response.headers.update({"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer",
                             "X-Frame-Options": "DENY", "X-Robots-Tag": "noindex, noarchive"})
    return response


@blueprint.post("/run")
def run():
    if not execution_enabled(): abort(403)
    if not request.is_secure and request.remote_addr not in ("127.0.0.1", "::1"):
        abort(403)
    supplied = request.form.get("execution_token", "")
    if not hmac.compare_digest(supplied.encode(), current_app.config["ANNOTATION_UI_TOKEN"].encode()): abort(403)
    require_csrf("annotation_csrf")
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


@blueprint.route("/review/<uuid:annotation_id>", methods=("GET", "POST"))
def review(annotation_id):
    # A lightweight lookup establishes the true layer; posted labels/identity never do.
    selected = service().review_record(annotation_id)
    if selected is None:
        abort(404)
    filters = result_filters(selected["annotation"].layer)
    if selected["annotation"].layer == "L2":
        if filters.get("pending"):
            abort(400)
        filters["mode"] = filters["mode"] or ("weak" if selected["annotation"].method_name == "gbv_relevance_weak_supervision" else "model")
    page = max(request.args.get("page", 1, type=int), 1)
    context = dict(filters, page=page)
    authorized = review_authenticated()
    status, error, form = 200, None, {}
    if request.method == "POST":
        if not review_enabled() or not local_review_request():
            abort(403)
        require_csrf("human_review_csrf")
        action = request.form.get("action", "")
        if action == "unlock":
            unlock_review(request.form.get("review_token", ""))
            session.pop("human_review_csrf", None)
            return redirect(url_for("annotations.review", annotation_id=annotation_id, **context), code=303)
        if not authorized:
            abort(403)
        if action == "lock":
            session.pop("human_review_binding", None)
            session.pop("human_review_started", None)
            session.pop("human_review_csrf", None)
            return redirect(url_for("annotations.review", annotation_id=annotation_id, **context), code=303)
        if action not in ("save", "save_next"):
            abort(400)
        form = {key: request.form.get(key, "") for key in
                ("decision", "human_label", "error_category", "reason", "notes")}
        data = service().review_detail(annotation_id, filters, current_app.config["PER_PAGE"])
        try:
            service().save_review(annotation_id, form, current_app.config["HUMAN_REVIEWER_ID"],
                                  current_app.config["HUMAN_REVIEW_GUIDELINE_VERSION"],
                                  request.form.get("expected_current_id", ""))
        except ReviewConflict as exc:
            error, status = str(exc), 409
        except ValueError as exc:
            error, status = str(exc), 422
        except SQLAlchemyError as exc:
            current_app.logger.warning("human_review_save_failed error_type=%s", type(exc).__name__)
            error, status = "Review could not be saved. Check infrastructure; your machine annotation is unchanged.", 503
        except RuntimeError:
            error, status = "Human Review is unavailable. Apply the human-validation migration for this layer and restart the app.", 503
        else:
            session.pop("human_review_csrf", None)
            flash("Human review saved separately; machine annotation is unchanged.", "success")
            neighbor = data["neighbors"]
            if action == "save_next" and neighbor["next_id"]:
                if filters.get("review_status"):
                    # Saving may remove this item from the pending/status cohort.
                    target = service().review_detail(neighbor["next_id"], filters, current_app.config["PER_PAGE"])
                    position = target["neighbors"]["position"]
                    if position:
                        neighbor["next_page"] = (position - 1) // current_app.config["PER_PAGE"] + 1
                return redirect(url_for("annotations.review", annotation_id=neighbor["next_id"],
                    **dict(context, page=neighbor["next_page"])), code=303)
            if action == "save_next":
                flash("End of the filtered review cohort.", "info")
                return redirect(url_for("annotations.results", layer=selected["annotation"].layer.lower(), **context), code=303)
            return redirect(url_for("annotations.review", annotation_id=annotation_id, **context), code=303)
    data = service().review_detail(annotation_id, filters, current_app.config["PER_PAGE"])
    # Only unlocked local sessions fetch full text and see private notes/identity.
    if authorized:
        data.update(service().review_content(data))
    response = current_app.make_response((render_template("annotations/review.html", **data,
        filters=filters, page=page, context=context, authorized=authorized,
        access_enabled=review_enabled() and local_review_request(),
        csrf=csrf_token("human_review_csrf") if review_enabled() and local_review_request() else None,
        labels=LABELS[selected["annotation"].layer], decisions=DECISIONS,
        error_categories=ERROR_CATEGORIES, status_labels=STATUSES, error=error, form=form,
        reviewer_identity=current_app.config["HUMAN_REVIEWER_ID"] if authorized else None,
        guideline_version=current_app.config["HUMAN_REVIEW_GUIDELINE_VERSION"] if authorized else None), status))
    response.headers.update({"Cache-Control": "private, no-store", "Referrer-Policy": "no-referrer",
        "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY", "X-Robots-Tag": "noindex, noarchive"})
    return response
