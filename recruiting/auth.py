from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from functools import wraps

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from .db import get_db, transaction

bp = Blueprint("auth", __name__, url_prefix="/auth")
ROLES = ("Candidate", "Employer")


@bp.before_app_request
def load_logged_in_user() -> None:
    user_id = session.get("user_id")
    if user_id is None:
        g.user = None
        return
    g.user = get_db().execute(
        "SELECT id, username, role FROM users WHERE id = ?",
        (user_id,),
    ).fetchone()
    if g.user is None:
        session.clear()


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            return redirect(url_for("auth.login"))
        return view(*args, **kwargs)

    return wrapped


def role_required(role: str):
    if role not in ROLES:
        raise ValueError("Unknown role")

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if g.user is None:
                return redirect(url_for("auth.login"))
            if g.user["role"] != role:
                abort(403, description=f"{role} role required")
            return view(*args, **kwargs)

        return wrapped

    return decorator


@bp.route("/register", methods=("GET", "POST"))
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        role = request.form.get("role", "")
        error = None
        if not username:
            error = "Username is required."
        elif len(username) > 80:
            error = "Username is too long."
        elif len(password) < 8:
            error = "Password must be at least 8 characters."
        elif role not in ROLES:
            error = "Role must be Candidate or Employer."

        if error is None:
            db = get_db()
            try:
                with transaction(db):
                    cursor = db.execute(
                        """
                        INSERT INTO users(username, password_hash, role, created_at)
                        VALUES (?, ?, ?, ?)
                        """,
                        (
                            username,
                            generate_password_hash(password, method="scrypt"),
                            role,
                            datetime.now(timezone.utc).isoformat(timespec="seconds"),
                        ),
                    )
                    user_id = int(cursor.lastrowid)
                    if role == "Candidate":
                        db.execute(
                            """
                            INSERT INTO candidate_profiles(user_id, display_name, skills_json, resume_text)
                            VALUES (?, ?, '[]', '')
                            """,
                            (user_id, username),
                        )
                    else:
                        db.execute(
                            """
                            INSERT INTO company_profiles(user_id, company_name, description)
                            VALUES (?, ?, '')
                            """,
                            (user_id, username),
                        )
            except sqlite3.IntegrityError:
                error = "Username already registered."
            else:
                flash("Registration complete. Please log in.", "success")
                return redirect(url_for("auth.login"))

        flash(error, "error")

    return render_template("auth/register.html", roles=ROLES)


@bp.route("/login", methods=("GET", "POST"))
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            "SELECT id, username, password_hash, role FROM users WHERE username = ?",
            (username,),
        ).fetchone()

        if user is None or not check_password_hash(user["password_hash"], password):
            flash("Invalid username or password.", "error")
        else:
            session.clear()
            session["user_id"] = user["id"]
            destination = "candidate.dashboard" if user["role"] == "Candidate" else "employer.dashboard"
            return redirect(url_for(destination))

    return render_template("auth/login.html")


@bp.post("/logout")
@login_required
def logout():
    session.clear()
    return redirect(url_for("home"))
