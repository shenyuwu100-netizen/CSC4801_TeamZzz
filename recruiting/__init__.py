from __future__ import annotations

import os
import secrets
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, render_template

from . import db


APP_TZ = ZoneInfo("Asia/Shanghai")


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    default_db = Path(os.environ.get("DATABASE_PATH", Path(app.instance_path) / "recruiting.sqlite3"))
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=str(default_db),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)

    Path(app.config["DATABASE"]).parent.mkdir(parents=True, exist_ok=True)
    db.init_app(app)

    from .auth import bp as auth_bp
    from .candidate import bp as candidate_bp
    from .employer import bp as employer_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(candidate_bp)
    app.register_blueprint(employer_bp)

    @app.get("/")
    def home():
        return render_template("home.html")

    @app.get("/healthz")
    def healthz():
        return jsonify(ok=True)

    @app.template_filter("localtime")
    def localtime(value: str | None) -> str:
        if not value:
            return "—"
        try:
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                return value
            return parsed.astimezone(APP_TZ).strftime("%Y-%m-%d %H:%M")
        except ValueError:
            return value

    @app.errorhandler(400)
    @app.errorhandler(403)
    @app.errorhandler(404)
    @app.errorhandler(409)
    def http_error(error):
        return render_template(
            "error.html",
            status=error.code,
            message=getattr(error, "description", "") or error.name,
        ), error.code

    with app.app_context():
        db.init_db()

    return app
