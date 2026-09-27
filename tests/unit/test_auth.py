from werkzeug.security import check_password_hash


def test_fp_auth_1_registration_and_session_lifecycle(client, db):
    response = client.post(
        "/auth/register",
        data={"username": "newcandidate", "password": "StrongPass123!", "role": "Candidate"},
    )
    assert response.status_code == 302
    user = db.execute(
        "SELECT id, role, password_hash FROM users WHERE username = ?",
        ("newcandidate",),
    ).fetchone()
    assert user is not None
    assert user["role"] == "Candidate"

    response = client.post(
        "/auth/login",
        data={"username": "newcandidate", "password": "StrongPass123!"},
    )
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/candidate/")
    with client.session_transaction() as session:
        assert session["user_id"] == user["id"]

    response = client.post("/auth/logout")
    assert response.status_code == 302
    with client.session_transaction() as session:
        assert "user_id" not in session


def test_fp_auth_1_invalid_registration(client, db):
    response = client.post(
        "/auth/register",
        data={"username": "badrole", "password": "StrongPass123!", "role": "Admin"},
    )
    assert response.status_code == 200
    assert db.execute("SELECT 1 FROM users WHERE username = 'badrole'").fetchone() is None

    response = client.post(
        "/auth/register",
        data={"username": "alice", "password": "StrongPass123!", "role": "Candidate"},
    )
    assert response.status_code == 200
    assert db.execute("SELECT COUNT(*) AS n FROM users WHERE username = 'alice'").fetchone()["n"] == 1

    response = client.post(
        "/auth/register",
        data={"username": "shortpw", "password": "123", "role": "Candidate"},
    )
    assert response.status_code == 200
    assert db.execute("SELECT 1 FROM users WHERE username = 'shortpw'").fetchone() is None


def test_fp_auth_2_salted_hash_and_password_verification(client, db):
    alice_hash = db.execute(
        "SELECT password_hash FROM users WHERE username = 'alice'"
    ).fetchone()["password_hash"]
    assert alice_hash != "DemoPass123!"
    assert check_password_hash(alice_hash, "DemoPass123!")

    client.post(
        "/auth/register",
        data={"username": "samepassword", "password": "DemoPass123!", "role": "Candidate"},
    )
    second_hash = db.execute(
        "SELECT password_hash FROM users WHERE username = 'samepassword'"
    ).fetchone()["password_hash"]
    assert second_hash != alice_hash
    assert check_password_hash(second_hash, "DemoPass123!")


def test_fp_auth_3_authorization_and_missing_object(client, login):
    response = client.get("/candidate/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]

    login("alice")
    assert client.get("/employer/").status_code == 403
    assert client.get("/candidate/jobs/999999").status_code == 404
