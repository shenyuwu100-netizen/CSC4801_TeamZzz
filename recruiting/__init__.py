from __future__ import annotations

import os
import secrets
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from flask import Flask, jsonify, redirect, render_template, request

from . import db
from .demo_guard import install_demo_guard


APP_TZ = ZoneInfo("Asia/Shanghai")


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__, instance_relative_config=True)
    default_db = Path(os.environ.get("DATABASE_PATH", Path(app.instance_path) / "recruiting.sqlite3"))
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("SECRET_KEY") or secrets.token_hex(32),
        DATABASE=str(default_db),
        DEMO_MODE=os.environ.get("DEMO_MODE", "").strip().lower() in {"1", "true", "yes", "on"},
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        SESSION_COOKIE_SECURE=os.environ.get("SESSION_COOKIE_SECURE", "").strip().lower()
        in {"1", "true", "yes", "on"},
        DEMO_LOGIN_PER_MINUTE=int(os.environ.get("DEMO_LOGIN_PER_MINUTE", "20")),
        DEMO_REGISTER_PER_MINUTE=int(os.environ.get("DEMO_REGISTER_PER_MINUTE", "8")),
        DEMO_WRITE_PER_MINUTE=int(os.environ.get("DEMO_WRITE_PER_MINUTE", "60")),
        DEMO_MAX_USERS=int(os.environ.get("DEMO_MAX_USERS", "100")),
        DEMO_MAX_JOBS=int(os.environ.get("DEMO_MAX_JOBS", "300")),
        DEMO_MAX_APPLICATIONS=int(os.environ.get("DEMO_MAX_APPLICATIONS", "2000")),
        DEMO_MAX_SLOTS=int(os.environ.get("DEMO_MAX_SLOTS", "1000")),
        DEMO_MAX_REQUEST_BYTES=int(os.environ.get("DEMO_MAX_REQUEST_BYTES", "65536")),
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
    install_demo_guard(app)

    @app.before_request
    def enforce_demo_https():
        forwarded_proto = request.headers.get("X-Forwarded-Proto", "").lower()
        cf_visitor = request.headers.get("CF-Visitor", "").replace(" ", "").lower()
        if app.config["DEMO_MODE"] and (
            forwarded_proto == "http" or '"scheme":"http"' in cf_visitor
        ):
            return redirect(request.url.replace("http://", "https://", 1), code=308)

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
    @app.errorhandler(413)
    @app.errorhandler(429)
    def http_error(error):
        return render_template(
            "error.html",
            status=error.code,
            message=getattr(error, "description", "") or error.name,
        ), error.code

    with app.app_context():
        db.init_db()

    return app
