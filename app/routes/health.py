from flask import Blueprint, current_app, render_template

blueprint = Blueprint("health", __name__)


@blueprint.get("/health")
def health():
    result = current_app.extensions["monitor_services"]["health"].health()
    return render_template("health.html", health=result), 200 if result["ok"] else 503
