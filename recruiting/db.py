from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

import click
from flask import Flask, current_app, g
from flask.cli import with_appcontext


def get_db() -> sqlite3.Connection:
    if "db" not in g:
        conn = sqlite3.connect(
            current_app.config["DATABASE"],
            detect_types=sqlite3.PARSE_DECLTYPES,
            timeout=10,
            isolation_level=None,
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA busy_timeout = 5000")
        g.db = conn
    return g.db


def close_db(_error=None) -> None:
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()


def _schema_text() -> str:
    return (Path(__file__).with_name("schema.sql")).read_text(encoding="utf-8")


def init_db() -> None:
    get_db().executescript(_schema_text())


def reset_db() -> None:
    conn = get_db()
    conn.executescript(
        """
        DROP TABLE IF EXISTS bookings;
        DROP TABLE IF EXISTS interview_slots;
        DROP TABLE IF EXISTS applications;
        DROP TABLE IF EXISTS jobs;
        DROP TABLE IF EXISTS company_profiles;
        DROP TABLE IF EXISTS candidate_profiles;
        DROP TABLE IF EXISTS users;
        """
    )
    conn.executescript(_schema_text())


@contextmanager
def transaction(conn: sqlite3.Connection, *, immediate: bool = False):
    conn.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
    try:
        yield
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    else:
        if conn.in_transaction:
            conn.execute("COMMIT")


@click.command("init-db")
@with_appcontext
def init_db_command() -> None:
    init_db()
    click.echo("Database schema initialized.")


@click.command("reset-seed")
@with_appcontext
def reset_seed_command() -> None:
    from .seed import seed_demo_data

    reset_db()
    seed_demo_data(get_db())
    click.echo("Database reset and deterministic demo data seeded.")


@click.command("ensure-demo-user")
@with_appcontext
def ensure_demo_user_command() -> None:
    from .seed import ensure_deployment_demo_user

    username = os.environ.get("DEMO_PERSONAL_USERNAME", "").strip()
    password = os.environ.get("DEMO_PERSONAL_PASSWORD", "")
    role = os.environ.get("DEMO_PERSONAL_ROLE", "Candidate").strip() or "Candidate"
    if not username and not password:
        click.echo("No deployment demo user configured; skipping.")
        return
    if not username or not password:
        raise click.ClickException("Both DEMO_PERSONAL_USERNAME and DEMO_PERSONAL_PASSWORD are required")

    try:
        ensure_deployment_demo_user(get_db(), username=username, password=password, role=role)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    click.echo("Deployment demo user ensured.")


def init_app(app: Flask) -> None:
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
    app.cli.add_command(reset_seed_command)
    app.cli.add_command(ensure_demo_user_command)
