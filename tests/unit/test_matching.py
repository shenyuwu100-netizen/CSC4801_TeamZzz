from recruiting.db import transaction
from recruiting.matching import rank_applicants, rank_jobs, skill_match_score, skills_to_json


def test_fp_match_1_examples_normalization_and_floor():
    assert skill_match_score(["Python", "SQL"], ["Python", "SQL"]) == 100
    assert skill_match_score(["Python"], ["Python", "SQL"]) == 50
    assert skill_match_score(["Rust"], ["Python", "SQL"]) == 0
    assert skill_match_score(["anything"], []) == 100
    assert skill_match_score([" Python ", "python", "SQL"], ["PYTHON", " sql ", "SQL"]) == 100
    assert skill_match_score(["A"], ["A", "B", "C"]) == 33


def test_fp_match_1_both_tie_breakers(db, ids):
    with transaction(db):
        first_alpha = db.execute(
            """
            INSERT INTO jobs(employer_id, title, description, required_skills_json, created_at)
            VALUES (?, 'Alpha', 'tie job', '[]', '2026-01-01T00:00:00+00:00')
            """,
            (ids["acme"],),
        ).lastrowid
        second_alpha = db.execute(
            """
            INSERT INTO jobs(employer_id, title, description, required_skills_json, created_at)
            VALUES (?, 'alpha', 'tie job', '[]', '2026-01-01T00:00:00+00:00')
            """,
            (ids["acme"],),
        ).lastrowid
        beta = db.execute(
            """
            INSERT INTO jobs(employer_id, title, description, required_skills_json, created_at)
            VALUES (?, 'Beta', 'tie job', '[]', '2026-01-01T00:00:00+00:00')
            """,
            (ids["acme"],),
        ).lastrowid

    ranked = [item for item in rank_jobs(db, ids["alice"]) if item["id"] in {first_alpha, second_alpha, beta}]
    assert [item["id"] for item in ranked] == [first_alpha, second_alpha, beta]

    with transaction(db):
        c1 = db.execute(
            "INSERT INTO users(username,password_hash,role,created_at) VALUES ('tie1','x','Candidate','x')"
        ).lastrowid
        c2 = db.execute(
            "INSERT INTO users(username,password_hash,role,created_at) VALUES ('tie2','x','Candidate','x')"
        ).lastrowid
        c3 = db.execute(
            "INSERT INTO users(username,password_hash,role,created_at) VALUES ('tie3','x','Candidate','x')"
        ).lastrowid
        db.execute(
            "INSERT INTO candidate_profiles(user_id,display_name,skills_json,resume_text) VALUES (?,?,?, '')",
            (c1, "Adam", skills_to_json(["Python", "SQL"])),
        )
        db.execute(
            "INSERT INTO candidate_profiles(user_id,display_name,skills_json,resume_text) VALUES (?,?,?, '')",
            (c2, "adam", skills_to_json(["Python", "SQL"])),
        )
        db.execute(
            "INSERT INTO candidate_profiles(user_id,display_name,skills_json,resume_text) VALUES (?,?,?, '')",
            (c3, "Zoe", skills_to_json(["Python", "SQL"])),
        )
        for candidate in (c1, c2, c3):
            db.execute(
                "INSERT INTO applications(candidate_id,job_id,status,created_at) VALUES (?,?,'Pending','x')",
                (candidate, ids["backend"]),
            )

    applicants = [
        item for item in rank_applicants(db, ids["backend"])
        if item["candidate_id"] in {c1, c2, c3}
    ]
    assert [item["candidate_id"] for item in applicants] == [c1, c2, c3]
