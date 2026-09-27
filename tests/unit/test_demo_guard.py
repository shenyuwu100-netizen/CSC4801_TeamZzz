from recruiting import create_app
from recruiting.db import get_db


def _demo_app(tmp_path, **overrides):
    config = {
        "TESTING": True,
        "DATABASE": str(tmp_path / "guard.sqlite3"),
        "SECRET_KEY": "guard-test-secret",
        "DEMO_MODE": True,
        "SESSION_COOKIE_SECURE": False,
        "DEMO_LOGIN_PER_MINUTE": 2,
        "DEMO_REGISTER_PER_MINUTE": 2,
        "DEMO_WRITE_PER_MINUTE": 2,
        "DEMO_MAX_USERS": 2,
        "DEMO_MAX_JOBS": 2,
        "DEMO_MAX_APPLICATIONS": 2,
        "DEMO_MAX_SLOTS": 2,
        "DEMO_MAX_REQUEST_BYTES": 1024,
    }
    config.update(overrides)
    return create_app(config)


def test_demo_login_rate_limit_returns_429(tmp_path):
    app = _demo_app(tmp_path)
    client = app.test_client()

    for _ in range(2):
        response = client.post(
            "/auth/login",
            data={"username": "missing", "password": "wrong"},
            headers={"CF-Connecting-IP": "203.0.113.10"},
        )
        assert response.status_code == 200

    limited = client.post(
        "/auth/login",
        data={"username": "missing", "password": "wrong"},
        headers={"CF-Connecting-IP": "203.0.113.10"},
    )
    assert limited.status_code == 429


def test_demo_register_rate_limit_is_per_client_ip(tmp_path):
    app = _demo_app(tmp_path, DEMO_MAX_USERS=20)
    client = app.test_client()

    for index in range(2):
        response = client.post(
            "/auth/register",
            data={
                "username": f"user-{index}",
                "password": "StrongPass123!",
                "role": "Candidate",
            },
            headers={"CF-Connecting-IP": "203.0.113.20"},
        )
        assert response.status_code == 302

    limited = client.post(
        "/auth/register",
        data={"username": "blocked", "password": "StrongPass123!", "role": "Candidate"},
        headers={"CF-Connecting-IP": "203.0.113.20"},
    )
    assert limited.status_code == 429

    other_ip = client.post(
        "/auth/register",
        data={"username": "other-ip", "password": "StrongPass123!", "role": "Candidate"},
        headers={"CF-Connecting-IP": "203.0.113.21"},
    )
    assert other_ip.status_code == 302


def test_demo_registration_capacity_blocks_growth(tmp_path):
    app = _demo_app(tmp_path, DEMO_REGISTER_PER_MINUTE=20)
    client = app.test_client()

    for index in range(2):
        response = client.post(
            "/auth/register",
            data={
                "username": f"capacity-{index}",
                "password": "StrongPass123!",
                "role": "Candidate",
            },
            headers={"CF-Connecting-IP": f"203.0.113.{30 + index}"},
        )
        assert response.status_code == 302

    blocked = client.post(
        "/auth/register",
        data={"username": "capacity-blocked", "password": "StrongPass123!", "role": "Candidate"},
        headers={"CF-Connecting-IP": "203.0.113.40"},
    )
    assert blocked.status_code == 429

    with app.app_context():
        assert get_db().execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"] == 2


def test_demo_request_body_limit_does_not_affect_normal_app(tmp_path):
    demo = _demo_app(tmp_path)
    demo_response = demo.test_client().post(
        "/auth/login",
        data={"username": "x" * 2000, "password": "wrong"},
    )
    assert demo_response.status_code == 413

    normal = create_app(
        {
            "TESTING": True,
            "DATABASE": str(tmp_path / "normal.sqlite3"),
            "SECRET_KEY": "normal-test-secret",
            "DEMO_MODE": False,
            "DEMO_MAX_REQUEST_BYTES": 64,
        }
    )
    normal_response = normal.test_client().post(
        "/auth/login",
        data={"username": "x" * 2000, "password": "wrong"},
    )
    assert normal_response.status_code == 200


def test_demo_write_rate_limit_applies_after_login(tmp_path):
    app = _demo_app(tmp_path, DEMO_MAX_USERS=20)
    client = app.test_client()

    register = client.post(
        "/auth/register",
        data={"username": "writer", "password": "StrongPass123!", "role": "Candidate"},
        headers={"CF-Connecting-IP": "203.0.113.50"},
    )
    assert register.status_code == 302
    login = client.post(
        "/auth/login",
        data={"username": "writer", "password": "StrongPass123!"},
        headers={"CF-Connecting-IP": "203.0.113.50"},
    )
    assert login.status_code == 302

    for index in range(2):
        response = client.post(
            "/candidate/profile",
            data={"display_name": f"Writer {index}", "skills": "Python"},
            headers={"CF-Connecting-IP": "203.0.113.50"},
        )
        assert response.status_code == 302

    limited = client.post(
        "/candidate/profile",
        data={"display_name": "Blocked", "skills": "Python"},
        headers={"CF-Connecting-IP": "203.0.113.50"},
    )
    assert limited.status_code == 429
