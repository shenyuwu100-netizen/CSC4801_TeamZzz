from datetime import datetime, timedelta, timezone

import pytest

from recruiting.db import transaction
from recruiting.services import DomainError, book_slot, create_slot, delete_slot, update_application_status


def _race_slot(db, ids):
    return db.execute(
        "SELECT id FROM interview_slots WHERE job_id = ? AND start_at = '2099-01-01T10:00:00+00:00'",
        (ids["backend"],),
    ).fetchone()["id"]


def test_fp_sched_1_slot_creation_timezones_and_deletion(db, ids):
    start = datetime(2099, 2, 1, 10, 0, tzinfo=timezone.utc)
    end = start + timedelta(minutes=30)
    slot_id = create_slot(db, ids["acme"], ids["backend"], start, end)
    row = db.execute("SELECT * FROM interview_slots WHERE id = ?", (slot_id,)).fetchone()
    assert row["employer_id"] == ids["acme"]
    assert datetime.fromisoformat(row["end_at"]) - datetime.fromisoformat(row["start_at"]) == timedelta(minutes=30)

    delete_slot(db, ids["acme"], slot_id)
    assert db.execute("SELECT 1 FROM interview_slots WHERE id = ?", (slot_id,)).fetchone() is None

    booked = db.execute(
        """
        SELECT s.id FROM interview_slots s
        JOIN bookings b ON b.slot_id = s.id
        LIMIT 1
        """
    ).fetchone()["id"]
    with pytest.raises(DomainError) as exc:
        delete_slot(db, ids["acme"], booked)
    assert exc.value.status_code == 409

    with pytest.raises(DomainError) as wrong_owner:
        delete_slot(db, ids["beta"], booked)
    assert wrong_owner.value.status_code == 403


def test_fp_sched_1_invalid_slots(db, ids):
    future = datetime(2099, 3, 1, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(DomainError) as wrong_duration:
        create_slot(db, ids["acme"], ids["backend"], future, future + timedelta(minutes=45))
    assert wrong_duration.value.status_code == 400

    with pytest.raises(DomainError) as backwards:
        create_slot(db, ids["acme"], ids["backend"], future, future - timedelta(minutes=30))
    assert backwards.value.status_code == 400

    past = datetime(2020, 1, 1, tzinfo=timezone.utc)
    with pytest.raises(DomainError) as old:
        create_slot(db, ids["acme"], ids["backend"], past, past + timedelta(minutes=30))
    assert old.value.status_code == 400

    with pytest.raises(DomainError) as wrong_owner:
        create_slot(
            db,
            ids["beta"],
            ids["backend"],
            future,
            future + timedelta(minutes=30),
        )
    assert wrong_owner.value.status_code == 403


def test_fp_sched_2_eligible_booking(db, ids):
    slot_id = _race_slot(db, ids)
    booking_id = book_slot(
        db,
        ids["bob"],
        ids["bob_backend"],
        slot_id,
        now=datetime(2026, 9, 27, tzinfo=timezone.utc),
    )
    booking = db.execute(
        "SELECT * FROM bookings WHERE id = ?",
        (booking_id,),
    ).fetchone()
    assert booking["application_id"] == ids["bob_backend"]
    assert booking["slot_id"] == slot_id

    with transaction(db):
        second_slot = db.execute(
            """
            INSERT INTO interview_slots(job_id, employer_id, start_at, end_at)
            VALUES (?, ?, '2099-01-03T10:00:00+00:00', '2099-01-03T10:30:00+00:00')
            """,
            (ids["backend"], ids["acme"]),
        ).lastrowid
    with pytest.raises(DomainError) as duplicate_booking:
        book_slot(
            db,
            ids["bob"],
            ids["bob_backend"],
            second_slot,
            now=datetime(2026, 9, 27, tzinfo=timezone.utc),
        )
    assert duplicate_booking.value.status_code == 409
    assert duplicate_booking.value.message == "Application already has interview booking"

    update_application_status(db, ids["acme"], ids["bob_backend"], "Accepted")
    still_booked = db.execute(
        "SELECT slot_id FROM bookings WHERE application_id = ?",
        (ids["bob_backend"],),
    ).fetchone()
    assert still_booked["slot_id"] == slot_id


def test_fp_sched_2_ineligible_booking(db, ids):
    slot_id = _race_slot(db, ids)
    with pytest.raises(DomainError) as other_candidate:
        book_slot(db, ids["carol"], ids["bob_backend"], slot_id)
    assert other_candidate.value.status_code == 403

    with pytest.raises(DomainError) as wrong_status:
        book_slot(db, ids["alice"], ids["alice_open"], slot_id)
    assert wrong_status.value.status_code in {403, 409}

    with transaction(db):
        beta_slot = db.execute(
            """
            INSERT INTO interview_slots(job_id, employer_id, start_at, end_at)
            VALUES (?, ?, '2099-03-01T10:00:00+00:00', '2099-03-01T10:30:00+00:00')
            """,
            (ids["open_role"], ids["beta"]),
        ).lastrowid
    with pytest.raises(DomainError) as wrong_employer:
        book_slot(db, ids["bob"], ids["bob_backend"], beta_slot)
    assert wrong_employer.value.status_code == 403


def test_fp_sched_2_booking_is_visible_and_booked_slot_is_hidden(client, login, db, ids):
    slot_id = _race_slot(db, ids)
    login("bob")
    response = client.post(
        f"/candidate/applications/{ids['bob_backend']}/book/{slot_id}",
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Interview booked" in response.get_data(as_text=True)
    assert "2099-01-01 18:00" in response.get_data(as_text=True)

    client.post("/auth/logout")
    login("acme")
    employer_view = client.get(f"/employer/jobs/{ids['backend']}/applicants")
    assert employer_view.status_code == 200
    employer_html = employer_view.get_data(as_text=True)
    assert "Bob Python" in employer_html
    assert "2099-01-01 18:00" in employer_html

    client.post("/auth/logout")
    login("dave")
    dave_view = client.get(f"/candidate/applications/{ids['dave_backend']}")
    assert dave_view.status_code == 200
    assert "2099-01-01 18:00" not in dave_view.get_data(as_text=True)


def test_fp_sched_3_conflict_contract(db, ids):
    slot_id = _race_slot(db, ids)
    first = book_slot(
        db,
        ids["bob"],
        ids["bob_backend"],
        slot_id,
        now=datetime(2026, 9, 27, tzinfo=timezone.utc),
    )
    assert first

    with pytest.raises(DomainError) as conflict:
        book_slot(
            db,
            ids["dave"],
            ids["dave_backend"],
            slot_id,
            now=datetime(2026, 9, 27, tzinfo=timezone.utc),
        )
    assert conflict.value.status_code == 409
    assert conflict.value.message == "Slot already booked"
    assert db.execute(
        "SELECT COUNT(*) AS n FROM bookings WHERE slot_id = ?",
        (slot_id,),
    ).fetchone()["n"] == 1
