from __future__ import annotations

import pytest

from recruiting import create_app
from recruiting.db import get_db, reset_db
from recruiting.seed import DEMO_PASSWORD, seed_demo_data


@pytest.fixture()
def app(tmp_path):
    database = tmp_path / "test.sqlite3"
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(database),
            "SECRET_KEY": "unit-test-secret",
        }
    )
    with app.app_context():
        reset_db()
        seed_demo_data(get_db())
    yield app


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def db(app):
    with app.app_context():
        yield get_db()


@pytest.fixture()
def ids(db):
    def user(name):
        return db.execute("SELECT id FROM users WHERE username = ?", (name,)).fetchone()["id"]

    def job(title):
        return db.execute("SELECT id FROM jobs WHERE title = ?", (title,)).fetchone()["id"]

    def application(candidate, job_title):
        return db.execute(
            """
            SELECT a.id FROM applications a
            JOIN users u ON u.id = a.candidate_id
            JOIN jobs j ON j.id = a.job_id
            WHERE u.username = ? AND j.title = ?
            """,
            (candidate, job_title),
        ).fetchone()["id"]

    return {
        "alice": user("alice"),
        "bob": user("bob"),
        "carol": user("carol"),
        "dave": user("dave"),
        "acme": user("acme"),
        "beta": user("beta"),
        "backend": job("Backend Engineer"),
        "open_role": job("Open Skills Role"),
        "alice_backend": application("alice", "Backend Engineer"),
        "bob_backend": application("bob", "Backend Engineer"),
        "carol_backend": application("carol", "Backend Engineer"),
        "dave_backend": application("dave", "Backend Engineer"),
        "alice_open": application("alice", "Open Skills Role"),
    }


@pytest.fixture()
def login(client):
    def do_login(username: str, password: str = DEMO_PASSWORD):
        return client.post(
            "/auth/login",
            data={"username": username, "password": password},
            follow_redirects=False,
        )

    return do_login
