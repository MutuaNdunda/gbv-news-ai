from uuid import UUID

from flask import Blueprint, abort, current_app, render_template, request

blueprint = Blueprint("articles", __name__, url_prefix="/articles")


@blueprint.get("")
def index():
    page = max(request.args.get("page", 1, type=int), 1)
    filters = {key: request.args.get(key, "").strip()
               for key in ("q", "source", "month", "date", "run_id", "parser_version", "kenya_relevance")}
    rows, total, runs, parsers = current_app.extensions["monitor_services"]["articles"].list(
        filters, page, current_app.config["PER_PAGE"]
    )
    return render_template("articles/index.html", rows=rows, total=total, page=page,
                           filters=filters, runs=runs, parsers=parsers)


@blueprint.get("/<uuid:article_id>")
def detail(article_id: UUID):
    data = current_app.extensions["monitor_services"]["articles"].detail(article_id)
    if data is None:
        abort(404)
    return render_template("articles/detail.html", **data)
