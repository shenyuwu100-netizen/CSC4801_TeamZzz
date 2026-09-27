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
