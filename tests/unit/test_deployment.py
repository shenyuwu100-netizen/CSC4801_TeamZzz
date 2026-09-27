from werkzeug.security import check_password_hash

from recruiting.db import get_db


def test_ensure_demo_user_cli_creates_private_candidate(app, monkeypatch):
    monkeypatch.setenv("DEMO_PERSONAL_USERNAME", "owner-demo")
    monkeypatch.setenv("DEMO_PERSONAL_PASSWORD", "StrongDemo123!")
    monkeypatch.setenv("DEMO_PERSONAL_ROLE", "Candidate")

    result = app.test_cli_runner().invoke(args=["ensure-demo-user"])
    assert result.exit_code == 0
    assert "Deployment demo user ensured." in result.output

    with app.app_context():
        user = get_db().execute(
            "SELECT id, password_hash, role FROM users WHERE username = ?",
            ("owner-demo",),
        ).fetchone()
        assert user is not None
        assert user["role"] == "Candidate"
        assert check_password_hash(user["password_hash"], "StrongDemo123!")

        profile = get_db().execute(
            "SELECT display_name, skills_json, resume_text FROM candidate_profiles WHERE user_id = ?",
            (user["id"],),
        ).fetchone()
        assert dict(profile) == {
            "display_name": "Owner Demo",
            "skills_json": "[]",
            "resume_text": "",
        }


def test_ensure_demo_user_cli_is_optional(app, monkeypatch):
    monkeypatch.delenv("DEMO_PERSONAL_USERNAME", raising=False)
    monkeypatch.delenv("DEMO_PERSONAL_PASSWORD", raising=False)

    result = app.test_cli_runner().invoke(args=["ensure-demo-user"])
    assert result.exit_code == 0
    assert "skipping" in result.output.lower()


def test_bootstrap_demo_seeds_fresh_database_once(tmp_path, monkeypatch):
    from recruiting import create_app

    monkeypatch.delenv("DEMO_PERSONAL_USERNAME", raising=False)
    monkeypatch.delenv("DEMO_PERSONAL_PASSWORD", raising=False)
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "bootstrap.sqlite3"),
            "SECRET_KEY": "bootstrap-test-secret",
        }
    )

    first = app.test_cli_runner().invoke(args=["bootstrap-demo"])
    assert first.exit_code == 0
    assert "Fresh demo database seeded." in first.output

    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 6
        get_db().execute(
            "UPDATE candidate_profiles SET display_name = 'Persistent Alice' WHERE user_id = "
            "(SELECT id FROM users WHERE username = 'alice')"
        )

    second = app.test_cli_runner().invoke(args=["bootstrap-demo"])
    assert second.exit_code == 0
    assert "Existing demo database preserved." in second.output

    with app.app_context():
        display_name = get_db().execute(
            "SELECT display_name FROM candidate_profiles WHERE user_id = "
            "(SELECT id FROM users WHERE username = 'alice')"
        ).fetchone()["display_name"]
        assert display_name == "Persistent Alice"
