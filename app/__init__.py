"""Collection/annotation monitor with optional protected bounded execution."""

import logging
import os

from flask import Flask
from flask.logging import default_handler

from database.session import create_session_factory, load_environment
from storage import GCSStorage
from app.services.article_service import ArticleService
from app.services.dashboard_service import DashboardService
from app.services.run_service import RunService
from app.services.storage_service import StorageService
from app.services.annotation_service import AnnotationService


def create_app(config=None, services=None):
    app = Flask(__name__)
    load_environment()
    app.config.from_mapping(PER_PAGE=25, ANNOTATION_UI_ENABLED=os.environ.get("ANNOTATION_UI_ENABLED") == "1",
                            ANNOTATION_UI_TOKEN=os.environ.get("ANNOTATION_UI_TOKEN", ""),
                            HUMAN_REVIEW_ENABLED=os.environ.get("HUMAN_REVIEW_ENABLED") == "1",
                            HUMAN_REVIEW_TOKEN=os.environ.get("HUMAN_REVIEW_TOKEN", ""),
                            HUMAN_REVIEWER_ID=os.environ.get("HUMAN_REVIEWER_ID", ""),
                            HUMAN_REVIEW_GUIDELINE_VERSION=os.environ.get("HUMAN_REVIEW_GUIDELINE_VERSION", ""),
                            SECRET_KEY=os.environ.get("FLASK_SECRET_KEY"),
                            SESSION_COOKIE_HTTPONLY=True, SESSION_COOKIE_SAMESITE="Strict",
                            SESSION_COOKIE_SECURE=os.environ.get("GAE_ENV") == "standard",
                            MAX_CONTENT_LENGTH=16 * 1024)
    if config:
        app.config.update(config)
    annotation_logger = logging.getLogger("annotations.service")
    if not annotation_logger.handlers:
        annotation_logger.addHandler(default_handler)
    annotation_logger.setLevel(logging.INFO)
    annotation_logger.propagate = False
    if services is None:
        sessions = create_session_factory()
        objects = GCSStorage()
        services = {
            "dashboard": DashboardService(sessions),
            "runs": RunService(sessions),
            "articles": ArticleService(sessions),
            "health": StorageService(sessions, objects),
            "annotations": AnnotationService(sessions, objects),
        }
    app.extensions["monitor_services"] = services

    from app.routes.articles import blueprint as articles
    from app.routes.dashboard import blueprint as dashboard
    from app.routes.health import blueprint as health
    from app.routes.runs import blueprint as runs
    from app.routes.annotations import blueprint as annotations

    app.register_blueprint(dashboard)
    app.register_blueprint(runs)
    app.register_blueprint(articles)
    app.register_blueprint(health)
    app.register_blueprint(annotations)
    return app
