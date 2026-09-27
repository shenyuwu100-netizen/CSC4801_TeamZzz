"""Regressions derived from REQUIREMENTS.md, using isolated real SQLite data."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Barrier

import pytest

from recruiting.db import get_db
from recruiting.matching import skill_match_score, skills_to_json
from recruiting.services import DomainError, book_slot, create_slot, delete_job, delete_slot


def _free_slot(db, ids):
    return db.execute(
        "SELECT s.id FROM interview_slots s LEFT JOIN bookings b ON b.slot_id=s.id "
        "WHERE s.employer_id=? AND b.id IS NULL ORDER BY s.id",
        (ids["acme"],),
    ).fetchone()["id"]


def _other_job(db, ids):
    return db.execute(
        "INSERT INTO jobs(employer_id,title,description,required_skills_json,created_at) "
        "VALUES (?, 'Second Acme Role', 'Another role', '[]', '2026-01-01T00:00:00+00:00')",
        (ids["acme"],),
    ).lastrowid


def test_fp_sched_2_same_employer_different_job_is_eligible(client, login, db, ids):
    other_job = _other_job(db, ids)
    start = datetime(2099, 6, 1, 10, tzinfo=timezone.utc)
    slot = create_slot(db, ids["acme"], other_job, start, start + timedelta(minutes=30))
    login("bob")
    booking_url = f"/candidate/applications/{ids['bob_backend']}/book/{slot}"
    detail = client.get(f"/candidate/applications/{ids['bob_backend']}")
    assert booking_url in detail.get_data(as_text=True)
    response = client.post(booking_url, follow_redirects=True)
    assert response.status_code == 200
    assert "2099-06-01 18:00" in response.get_data(as_text=True)
    assert db.execute("SELECT slot_id FROM bookings WHERE application_id=?",
                      (ids["bob_backend"],)).fetchone()["slot_id"] == slot
    client.post("/auth/logout")
    login("acme")
    assert "2099-06-01 18:00" in client.get(
        f"/employer/jobs/{ids['backend']}/applicants"
    ).get_data(as_text=True)
    client.post("/auth/logout")
    login("dave")
    assert f"/book/{slot}" not in client.get(
        f"/candidate/applications/{ids['dave_backend']}"
    ).get_data(as_text=True)


def test_fp_sched_2_same_employer_cross_job_service(db, ids):
    job = _other_job(db, ids)
    application = db.execute(
        "INSERT INTO applications(candidate_id,job_id,status,created_at) "
        "VALUES (?,?,'Interviewing','2026-01-01T00:00:00+00:00')",
        (ids["bob"], job),
    ).lastrowid
    slot = _free_slot(db, ids)
    booking = book_slot(db, ids["bob"], application, slot)
    assert db.execute("SELECT application_id FROM bookings WHERE id=?", (booking,)).fetchone()[0] == application


def test_fp_match_1_lowercase_does_not_merge_distinct_unicode_skills():
    # The normative oracle says lowercase, not Unicode case folding (ß -> ss).
    assert skill_match_score(["STRASSE"], ["Straße"]) == 0
    assert skill_match_score(["STRASSE"], ["Straße", "STRASSE"]) == 50
    assert skills_to_json(["Straße", "STRASSE"]) == '["Straße","STRASSE"]'


def test_fp_auth_3_ownership_precedes_status_validation(client, login, db, ids):
    login("beta")
    response = client.post(f"/employer/applications/{ids['bob_backend']}/status",
                           data={"status": "not-a-status"})
    assert response.status_code == 403
    assert db.execute("SELECT status FROM applications WHERE id=?",
                      (ids["bob_backend"],)).fetchone()["status"] == "Interviewing"


@pytest.mark.parametrize("job_key, expected", [("backend", 403), ("missing", 404), ("open_role", 400)])
def test_fp_auth_3_slot_owner_precedes_date_validation(client, login, db, ids, job_key, expected):
    login("beta")
    before = db.execute("SELECT COUNT(*) FROM interview_slots").fetchone()[0]
    response = client.post("/employer/slots", data={
        "job_id": ids.get(job_key, 999999), "start_at": "invalid", "end_at": "invalid",
    })
    assert response.status_code == expected
    assert db.execute("SELECT COUNT(*) FROM interview_slots").fetchone()[0] == before


class _ConcurrentWriteBeforeTransaction:
    """Yield once to another real DB connection before acquiring our write lock."""

    def __init__(self, connection, other_write):
        self.connection = connection
        self.other_write = other_write

    def __getattr__(self, name):
        return getattr(self.connection, name)

    def execute(self, sql, parameters=()):
        if sql.startswith("BEGIN") and self.other_write is not None:
            other_write, self.other_write = self.other_write, None
            other_write()
        return self.connection.execute(sql, parameters)


def test_fp_sched_1_booking_wins_against_slot_deletion(app, db, ids):
    slot = _free_slot(db, ids)

    def concurrent_booking():
        with app.app_context():
            book_slot(get_db(), ids["bob"], ids["bob_backend"], slot)

    connection = _ConcurrentWriteBeforeTransaction(db, concurrent_booking)
    with pytest.raises(DomainError) as conflict:
        delete_slot(connection, ids["acme"], slot)
    assert conflict.value.status_code == 409
    assert db.execute("SELECT 1 FROM interview_slots WHERE id=?", (slot,)).fetchone()
    assert db.execute("SELECT COUNT(*) FROM bookings WHERE slot_id=?", (slot,)).fetchone()[0] == 1
    assert not db.in_transaction


def test_fp_emp_2_application_wins_against_job_deletion(app, db, ids):
    job = _other_job(db, ids)

    def concurrent_application():
        with app.app_context():
            get_db().execute(
                "INSERT INTO applications(candidate_id,job_id,status,created_at) "
                "VALUES (?,?,'Pending','2026-01-01T00:00:00+00:00')", (ids["bob"], job)
            )

    connection = _ConcurrentWriteBeforeTransaction(db, concurrent_application)
    with pytest.raises(DomainError) as conflict:
        delete_job(connection, ids["acme"], job)
    assert conflict.value.status_code == 409
    assert db.execute("SELECT 1 FROM jobs WHERE id=?", (job,)).fetchone()
    assert db.execute("SELECT COUNT(*) FROM applications WHERE job_id=?", (job,)).fetchone()[0] == 1
    assert not db.in_transaction


def test_fp_sched_3_independent_connections_have_one_winner(app, db, ids):
    slot = _free_slot(db, ids)
    ready = Barrier(2)

    def attempt(candidate, application):
        with app.app_context():
            connection = get_db()
            ready.wait(timeout=10)
            try:
                book_slot(connection, candidate, application, slot)
                return 200, "booked"
            except DomainError as exc:
                return exc.status_code, exc.message

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(attempt, ids[candidate], ids[application])
                   for candidate, application in [("bob", "bob_backend"), ("dave", "dave_backend")]]
        results = [future.result(timeout=15) for future in futures]
    assert sorted(results) == [(200, "booked"), (409, "Slot already booked")]
    assert db.execute("SELECT COUNT(*) FROM bookings WHERE slot_id=?", (slot,)).fetchone()[0] == 1


@pytest.mark.parametrize("status", ["Pending", "Rejected", "Accepted"])
def test_fp_sched_2_ineligible_status_leaves_database_unchanged(db, ids, status):
    slot = _free_slot(db, ids)
    db.execute("UPDATE applications SET status=? WHERE id=?", (status, ids["bob_backend"]))
    before = [tuple(row) for row in db.execute("SELECT * FROM bookings ORDER BY id")]
    with pytest.raises(DomainError) as conflict:
        book_slot(db, ids["bob"], ids["bob_backend"], slot)
    assert conflict.value.status_code == 409
    assert conflict.value.message == "Application must be Interviewing"
    assert [tuple(row) for row in db.execute("SELECT * FROM bookings ORDER BY id")] == before
    assert not db.in_transaction


def test_fp_sched_2_expired_slot_leaves_database_unchanged(db, ids):
    slot = _free_slot(db, ids)
    before = [tuple(row) for row in db.execute("SELECT * FROM bookings ORDER BY id")]
    with pytest.raises(DomainError) as conflict:
        book_slot(db, ids["bob"], ids["bob_backend"], slot,
                  now=datetime(2099, 1, 1, 10, tzinfo=timezone.utc))
    assert conflict.value.status_code == 409
    assert conflict.value.message == "Interview slot is no longer in the future"
    assert [tuple(row) for row in db.execute("SELECT * FROM bookings ORDER BY id")] == before
    assert not db.in_transaction
