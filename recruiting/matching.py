from __future__ import annotations

import json
import re
from typing import Iterable


def normalize_skills(values: str | Iterable[str] | None) -> list[str]:
    if values is None:
        return []
    if isinstance(values, str):
        source = re.split(r"[,;\n]", values)
    else:
        source = list(values)

    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in source:
        value = str(raw).strip()
        key = value.lower()
        if value and key not in seen:
            cleaned.append(value)
            seen.add(key)
    return cleaned


def skills_to_json(values: str | Iterable[str] | None) -> str:
    return json.dumps(normalize_skills(values), ensure_ascii=False, separators=(",", ":"))


def skills_from_json(value: str | None) -> list[str]:
    try:
        raw = json.loads(value or "[]")
    except json.JSONDecodeError:
        return []
    if not isinstance(raw, list):
        return []
    return normalize_skills(raw)


def skill_match_score(candidate_skills, required_skills) -> int:
    candidate = {item.lower() for item in normalize_skills(candidate_skills)}
    required = {item.lower() for item in normalize_skills(required_skills)}
    if not required:
        return 100
    return (100 * len(candidate & required)) // len(required)


def rank_jobs(conn, candidate_id: int) -> list[dict]:
    profile = conn.execute(
        "SELECT skills_json FROM candidate_profiles WHERE user_id = ?",
        (candidate_id,),
    ).fetchone()
    candidate_skills = skills_from_json(profile["skills_json"] if profile else "[]")
    rows = conn.execute(
        """
        SELECT j.id, j.title, j.description, j.required_skills_json,
               j.employer_id, c.company_name
        FROM jobs AS j
        JOIN company_profiles AS c ON c.user_id = j.employer_id
        """
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["required_skills"] = skills_from_json(item.pop("required_skills_json"))
        item["match_score"] = skill_match_score(candidate_skills, item["required_skills"])
        result.append(item)
    result.sort(key=lambda item: (-item["match_score"], item["title"].casefold(), item["id"]))
    return result


def rank_applicants(conn, job_id: int) -> list[dict]:
    job = conn.execute(
        "SELECT id, required_skills_json FROM jobs WHERE id = ?",
        (job_id,),
    ).fetchone()
    if job is None:
        return []
    required_skills = skills_from_json(job["required_skills_json"])
    rows = conn.execute(
        """
        SELECT a.id AS application_id, a.candidate_id, a.status,
               u.username, p.display_name, p.skills_json,
               b.id AS booking_id, s.start_at AS interview_start,
               s.end_at AS interview_end
        FROM applications AS a
        JOIN users AS u ON u.id = a.candidate_id
        JOIN candidate_profiles AS p ON p.user_id = a.candidate_id
        LEFT JOIN bookings AS b ON b.application_id = a.id
        LEFT JOIN interview_slots AS s ON s.id = b.slot_id
        WHERE a.job_id = ?
        """,
        (job_id,),
    ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        item["skills"] = skills_from_json(item.pop("skills_json"))
        item["match_score"] = skill_match_score(item["skills"], required_skills)
        result.append(item)
    result.sort(
        key=lambda item: (
            -item["match_score"],
            item["display_name"].casefold(),
            item["candidate_id"],
        )
    )
    return result
