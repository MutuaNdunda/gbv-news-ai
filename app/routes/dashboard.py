from flask import Blueprint, current_app, render_template

blueprint = Blueprint("dashboard", __name__)


@blueprint.get("/")
def index():
    data = current_app.extensions["monitor_services"]["dashboard"].overview()
    return render_template("dashboard.html", **data)
