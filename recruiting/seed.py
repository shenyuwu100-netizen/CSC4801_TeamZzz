from __future__ import annotations

from datetime import datetime, timezone

from werkzeug.security import generate_password_hash

from .db import transaction
from .matching import skills_to_json


DEMO_PASSWORD = "DemoPass123!"


def seed_demo_data(conn) -> None:
    created = "2026-09-27T00:00:00+00:00"

    def add_user(username: str, role: str) -> int:
        cursor = conn.execute(
            "INSERT INTO users(username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
            (username, generate_password_hash(DEMO_PASSWORD, method="scrypt"), role, created),
        )
        return int(cursor.lastrowid)

    with transaction(conn):
        alice = add_user("alice", "Candidate")
        bob = add_user("bob", "Candidate")
        carol = add_user("carol", "Candidate")
        dave = add_user("dave", "Candidate")
        acme = add_user("acme", "Employer")
        beta = add_user("beta", "Employer")

        candidates = [
            (alice, "Alice Python", ["Python", "SQL"], "Backend candidate with Python and SQL."),
            (bob, "Bob Python", ["Python"], "Python developer."),
            (carol, "Carol Rust", ["Rust"], "Rust developer."),
            (dave, "Dave Go", ["Go"], "Go developer."),
        ]
        for user_id, display_name, skills, resume in candidates:
            conn.execute(
                """
                INSERT INTO candidate_profiles(user_id, display_name, skills_json, resume_text)
                VALUES (?, ?, ?, ?)
                """,
                (user_id, display_name, skills_to_json(skills), resume),
            )

        conn.execute(
            "INSERT INTO company_profiles(user_id, company_name, description) VALUES (?, ?, ?)",
            (acme, "Acme Analytics", "Builds data products."),
        )
        conn.execute(
            "INSERT INTO company_profiles(user_id, company_name, description) VALUES (?, ?, ?)",
            (beta, "Beta Labs", "Generalist technology studio."),
        )

        backend = conn.execute(
            """
            INSERT INTO jobs(employer_id, title, description, required_skills_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (acme, "Backend Engineer", "Build Python data services.", skills_to_json(["Python", "SQL"]), created),
        ).lastrowid
        open_role = conn.execute(
            """
            INSERT INTO jobs(employer_id, title, description, required_skills_json, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (beta, "Open Skills Role", "Open to candidates from any technical background.", skills_to_json([]), created),
        ).lastrowid

        accepted = conn.execute(
            "INSERT INTO applications(candidate_id, job_id, status, created_at) VALUES (?, ?, 'Accepted', ?)",
            (alice, backend, created),
        ).lastrowid
        conn.execute(
            "INSERT INTO applications(candidate_id, job_id, status, created_at) VALUES (?, ?, 'Interviewing', ?)",
            (bob, backend, created),
        )
        conn.execute(
            "INSERT INTO applications(candidate_id, job_id, status, created_at) VALUES (?, ?, 'Rejected', ?)",
            (carol, backend, created),
        )
        conn.execute(
            "INSERT INTO applications(candidate_id, job_id, status, created_at) VALUES (?, ?, 'Interviewing', ?)",
            (dave, backend, created),
        )
        conn.execute(
            "INSERT INTO applications(candidate_id, job_id, status, created_at) VALUES (?, ?, 'Pending', ?)",
            (alice, open_role, created),
        )

        race_slot = conn.execute(
            """
            INSERT INTO interview_slots(job_id, employer_id, start_at, end_at)
            VALUES (?, ?, ?, ?)
            """,
            (backend, acme, "2099-01-01T10:00:00+00:00", "2099-01-01T10:30:00+00:00"),
        ).lastrowid
        historical_slot = conn.execute(
            """
            INSERT INTO interview_slots(job_id, employer_id, start_at, end_at)
            VALUES (?, ?, ?, ?)
            """,
            (backend, acme, "2099-01-02T10:00:00+00:00", "2099-01-02T10:30:00+00:00"),
        ).lastrowid
        conn.execute(
            "INSERT INTO bookings(application_id, slot_id, booked_at) VALUES (?, ?, ?)",
            (accepted, historical_slot, "2026-09-27T00:00:00+00:00"),
        )

        # Keep the unbooked race slot explicit: Bob and Dave are both Interviewing
        # on this job and therefore are eligible to compete for this same slot.
        assert race_slot
