"""Flask application factory for the read-only corpus collection monitor."""

from flask import Flask

from database.session import create_session_factory
from storage import GCSStorage
from app.services.article_service import ArticleService
from app.services.dashboard_service import DashboardService
from app.services.run_service import RunService
from app.services.storage_service import StorageService


def create_app(config=None, services=None):
    app = Flask(__name__)
    app.config.from_mapping(PER_PAGE=25)
    if config:
        app.config.update(config)
    if services is None:
        sessions = create_session_factory()
        objects = GCSStorage()
        services = {
            "dashboard": DashboardService(sessions),
            "runs": RunService(sessions),
            "articles": ArticleService(sessions),
            "health": StorageService(sessions, objects),
        }
    app.extensions["monitor_services"] = services

    from app.routes.articles import blueprint as articles
    from app.routes.dashboard import blueprint as dashboard
    from app.routes.health import blueprint as health
    from app.routes.runs import blueprint as runs

    app.register_blueprint(dashboard)
    app.register_blueprint(runs)
    app.register_blueprint(articles)
    app.register_blueprint(health)
    return app
