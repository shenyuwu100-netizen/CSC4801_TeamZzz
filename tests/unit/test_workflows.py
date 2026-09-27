from datetime import datetime, timezone

from recruiting.db import transaction
from recruiting.matching import rank_applicants, rank_jobs, skills_from_json
from recruiting.services import create_slot


def test_fp_can_1_profile_and_private_resume_rules(client, login, db, ids):
    login("alice")
    response = client.post(
        "/candidate/profile",
        data={"display_name": "Alice Updated", "skills": "Python, SQL, python, Docker"},
    )
    assert response.status_code == 302
    profile = db.execute(
        "SELECT display_name, skills_json FROM candidate_profiles WHERE user_id = ?",
        (ids["alice"],),
    ).fetchone()
    assert profile["display_name"] == "Alice Updated"
    assert skills_from_json(profile["skills_json"]) == ["Python", "SQL", "Docker"]
    backend = next(item for item in rank_jobs(db, ids["alice"]) if item["id"] == ids["backend"])
    assert backend["match_score"] == 100

    response = client.post(
        f"/candidate/resume/{ids['alice']}",
        data={"resume_text": "Private resume text"},
    )
    assert response.status_code == 302
    assert client.get(f"/candidate/resume/{ids['alice']}").status_code == 200

    client.post("/auth/logout")
    login("bob")
    assert client.get(f"/candidate/resume/{ids['alice']}").status_code == 403

    client.post("/auth/logout")
    login("acme")
    assert client.get(f"/candidate/resume/{ids['alice']}").status_code == 403


def test_fp_can_2_recommendations_preserve_fields_and_rank_all_jobs(db, ids):
    jobs = rank_jobs(db, ids["alice"])
    database_count = db.execute("SELECT COUNT(*) AS n FROM jobs").fetchone()["n"]
    assert len(jobs) == database_count
    assert jobs == sorted(jobs, key=lambda item: (-item["match_score"], item["title"].casefold(), item["id"]))
    backend = next(item for item in jobs if item["id"] == ids["backend"])
    assert backend["match_score"] == 100
    assert backend["title"] == "Backend Engineer"
    assert backend["company_name"] == "Acme Analytics"
    assert backend["required_skills"] == ["Python", "SQL"]
    assert backend["description"]


def test_fp_can_3_pending_duplicate_and_application_owner(client, login, db, ids):
    login("carol")
    response = client.post(f"/candidate/jobs/{ids['open_role']}/apply")
    assert response.status_code == 302
    application = db.execute(
        "SELECT id, status FROM applications WHERE candidate_id = ? AND job_id = ?",
        (ids["carol"], ids["open_role"]),
    ).fetchone()
    assert application["status"] == "Pending"

    duplicate = client.post(f"/candidate/jobs/{ids['open_role']}/apply")
    assert duplicate.status_code == 409
    assert db.execute(
        "SELECT COUNT(*) AS n FROM applications WHERE candidate_id = ? AND job_id = ?",
        (ids["carol"], ids["open_role"]),
    ).fetchone()["n"] == 1

    client.post("/auth/logout")
    login("bob")
    assert client.get(f"/candidate/applications/{application['id']}").status_code == 403
    assert client.post(
        f"/employer/applications/{ids['bob_backend']}/status",
        data={"status": "Accepted"},
    ).status_code == 403


def test_fp_emp_1_company_profile(client, login, db, ids):
    login("acme")
    response = client.post(
        "/employer/company",
        data={"company_name": "Acme Updated", "description": "Updated description <b>plain text</b>"},
    )
    assert response.status_code == 302
    company = db.execute(
        "SELECT company_name, description FROM company_profiles WHERE user_id = ?",
        (ids["acme"],),
    ).fetchone()
    assert company["company_name"] == "Acme Updated"
    assert company["description"] == "Updated description <b>plain text</b>"


def test_fp_emp_2_job_validation_and_deletion(client, login, db, ids):
    login("acme")
    invalid = client.post(
        "/employer/jobs/new",
        data={"title": "No description", "description": "", "required_skills": ""},
    )
    assert invalid.status_code == 400

    created = client.post(
        "/employer/jobs/new",
        data={"title": "Fresh Role", "description": "A valid role.", "required_skills": "Python"},
    )
    assert created.status_code == 302
    new_job = db.execute("SELECT * FROM jobs WHERE title = 'Fresh Role'").fetchone()
    assert new_job is not None

    edited = client.post(
        f"/employer/jobs/{new_job['id']}/edit",
        data={"title": "Fresh Role Edited", "description": "Updated.", "required_skills": "Go"},
    )
    assert edited.status_code == 302

    forbidden = client.get(f"/employer/jobs/{ids['open_role']}/edit")
    assert forbidden.status_code == 403

    blocked = client.post(f"/employer/jobs/{ids['backend']}/delete")
    assert blocked.status_code == 409
    assert db.execute("SELECT 1 FROM jobs WHERE id = ?", (ids["backend"],)).fetchone() is not None

    slot_only = client.post(
        "/employer/jobs/new",
        data={"title": "Slot Only Role", "description": "No applications yet.", "required_skills": ""},
    )
    assert slot_only.status_code == 302
    slot_only_id = db.execute("SELECT id FROM jobs WHERE title = 'Slot Only Role'").fetchone()["id"]
    create_slot(
        db,
        ids["acme"],
        slot_only_id,
        datetime(2099, 4, 1, 10, 0, tzinfo=timezone.utc),
        datetime(2099, 4, 1, 10, 30, tzinfo=timezone.utc),
    )
    assert client.post(f"/employer/jobs/{slot_only_id}/delete").status_code == 409

    deleted = client.post(f"/employer/jobs/{new_job['id']}/delete")
    assert deleted.status_code == 302
    assert db.execute("SELECT 1 FROM jobs WHERE id = ?", (new_job["id"],)).fetchone() is None


def test_fp_emp_3_applicant_fields_order_status_and_role(client, login, db, ids):
    applicants = rank_applicants(db, ids["backend"])
    assert applicants == sorted(
        applicants,
        key=lambda item: (-item["match_score"], item["display_name"].casefold(), item["candidate_id"]),
    )
    alice = next(item for item in applicants if item["candidate_id"] == ids["alice"])
    assert {"display_name", "skills", "match_score", "status", "interview_start"} <= set(alice)

    login("acme")
    response = client.post(
        f"/employer/applications/{ids['bob_backend']}/status",
        data={"status": "Accepted"},
    )
    assert response.status_code == 302
    assert db.execute(
        "SELECT status FROM applications WHERE id = ?",
        (ids["bob_backend"],),
    ).fetchone()["status"] == "Accepted"

    invalid = client.post(
        f"/employer/applications/{ids['carol_backend']}/status",
        data={"status": "Maybe"},
    )
    assert invalid.status_code == 400

    client.post("/auth/logout")
    login("beta")
    assert client.post(
        f"/employer/applications/{ids['carol_backend']}/status",
        data={"status": "Accepted"},
    ).status_code == 403
