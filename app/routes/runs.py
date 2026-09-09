from uuid import UUID

from flask import Blueprint, abort, current_app, render_template, request

blueprint = Blueprint("runs", __name__, url_prefix="/runs")


@blueprint.get("")
def index():
    page = max(request.args.get("page", 1, type=int), 1)
    rows, total = current_app.extensions["monitor_services"]["runs"].list(
        page, current_app.config["PER_PAGE"]
    )
    return render_template("runs/index.html", rows=rows, page=page, total=total)


@blueprint.get("/<uuid:run_id>")
def detail(run_id: UUID):
    data = current_app.extensions["monitor_services"]["runs"].detail(run_id)
    if data is None:
        abort(404)
    return render_template("runs/detail.html", **data)
