from pathlib import Path

from recruiting import create_app
from recruiting.db import transaction
from recruiting.services import search_jobs


def test_fp_sec_1_object_access_boundaries(client, login, ids):
    login("bob")
    assert client.get(f"/candidate/resume/{ids['alice']}").status_code == 403
    assert client.post(
        f"/candidate/resume/{ids['alice']}",
        data={"resume_text": "attempted overwrite"},
    ).status_code == 403
    assert client.get(f"/candidate/applications/{ids['alice_backend']}").status_code == 403
    assert client.post(
        f"/candidate/applications/{ids['alice_backend']}/book/1"
    ).status_code == 403

    client.post("/auth/logout")
    login("beta")
    assert client.get(f"/employer/jobs/{ids['backend']}/edit").status_code == 403
    assert client.post(
        f"/employer/jobs/{ids['backend']}/edit",
        data={"title": "tampered", "description": "tampered", "required_skills": ""},
    ).status_code == 403
    assert client.get(f"/employer/jobs/{ids['backend']}/applicants").status_code == 403


def test_fp_sec_2_sql_metacharacters_are_bound(db):
    before = db.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]
    payload = "' OR 1=1; DROP TABLE jobs; --"
    results = search_jobs(db, payload)
    assert results == []
    assert db.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"] == before

    with transaction(db):
        db.execute(
            "UPDATE candidate_profiles SET display_name = ? WHERE user_id = (SELECT id FROM users WHERE username='alice')",
            (payload,),
        )
    assert db.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] >= 1


def test_fp_sec_3_xss_is_escaped(client, login, db, ids):
    payload = "<script>alert(1)</script>"
    login("acme")
    response = client.post(
        "/employer/jobs/new",
        data={"title": payload, "description": payload, "required_skills": "Python"},
    )
    assert response.status_code == 302
    job_id = db.execute("SELECT id FROM jobs WHERE title = ?", (payload,)).fetchone()["id"]

    client.post("/auth/logout")
    login("alice")
    response = client.get(f"/candidate/jobs/{job_id}")
    html = response.get_data(as_text=True)
    assert payload not in html
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in html


def test_fp_sec_4_secrets_and_test_isolation(app):
    database = Path(app.config["DATABASE"])
    assert database.name == "test.sqlite3"
    assert app.config["TESTING"] is True

    env_example = Path(__file__).resolve().parents[2] / ".env.example"
    text = env_example.read_text(encoding="utf-8")
    assert "sk-" not in text
    assert "Bearer " not in text


def test_public_demo_banner_and_secure_session_cookie(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "demo.sqlite3"),
            "SECRET_KEY": "demo-test-secret",
            "DEMO_MODE": True,
            "SESSION_COOKIE_SECURE": True,
        }
    )
    client = app.test_client()

    homepage = client.get("/")
    assert "Public course demo" in homepage.get_data(as_text=True)

    insecure = client.get(
        "/",
        headers={"Host": "csc4801.wushenyu.com", "X-Forwarded-Proto": "http"},
    )
    assert insecure.status_code == 308
    assert insecure.headers["Location"] == "https://csc4801.wushenyu.com/"

    cloudflare_http = client.get(
        "/",
        headers={"Host": "csc4801.wushenyu.com", "CF-Visitor": '{"scheme":"http"}'},
    )
    assert cloudflare_http.status_code == 308
    assert cloudflare_http.headers["Location"] == "https://csc4801.wushenyu.com/"

    response = client.post(
        "/auth/register",
        data={"username": "secure-cookie", "password": "StrongPass123!", "role": "Candidate"},
    )
    assert response.status_code == 302
    assert "Secure" in response.headers.get("Set-Cookie", "")
