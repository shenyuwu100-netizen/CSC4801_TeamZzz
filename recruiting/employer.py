from __future__ import annotations

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from .auth import role_required
from .db import get_db, transaction
from .matching import rank_applicants, skills_from_json, skills_to_json
from .services import (
    DomainError,
    VALID_STATUSES,
    create_slot,
    delete_job,
    delete_slot,
    iso_utc,
    parse_local_datetime,
    update_application_status,
    utc_now,
)

bp = Blueprint("employer", __name__, url_prefix="/employer")


def _owned_job_or_error(job_id: int):
    job = get_db().execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        abort(404, description="Job not found")
    if job["employer_id"] != g.user["id"]:
        abort(403, description="Forbidden")
    return job


@bp.get("/")
@role_required("Employer")
def dashboard():
    db = get_db()
    company = db.execute(
        "SELECT company_name, description FROM company_profiles WHERE user_id = ?",
        (g.user["id"],),
    ).fetchone()
    jobs = db.execute(
        """
        SELECT j.*,
               (SELECT COUNT(*) FROM applications a WHERE a.job_id = j.id) AS application_count,
               (SELECT COUNT(*) FROM interview_slots s WHERE s.job_id = j.id) AS slot_count
        FROM jobs j
        WHERE j.employer_id = ?
        ORDER BY j.title COLLATE NOCASE, j.id
        """,
        (g.user["id"],),
    ).fetchall()
    slots = db.execute(
        """
        SELECT s.*, j.title,
               b.application_id
        FROM interview_slots s
        JOIN jobs j ON j.id = s.job_id
        LEFT JOIN bookings b ON b.slot_id = s.id
        WHERE s.employer_id = ?
        ORDER BY s.start_at, s.id
        """,
        (g.user["id"],),
    ).fetchall()
    return render_template("employer/dashboard.html", company=company, jobs=jobs, slots=slots)


@bp.route("/company", methods=("GET", "POST"))
@role_required("Employer")
def company():
    db = get_db()
    if request.method == "POST":
        company_name = request.form.get("company_name", "").strip()
        description = request.form.get("description", "")
        if not company_name:
            abort(400, description="Company name is required")
        with transaction(db):
            db.execute(
                "UPDATE company_profiles SET company_name = ?, description = ? WHERE user_id = ?",
                (company_name, description, g.user["id"]),
            )
        flash("Company profile updated.", "success")
        return redirect(url_for("employer.company"))

    row = db.execute(
        "SELECT company_name, description FROM company_profiles WHERE user_id = ?",
        (g.user["id"],),
    ).fetchone()
    return render_template("employer/company.html", company=row)


@bp.route("/jobs/new", methods=("GET", "POST"))
@role_required("Employer")
def job_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        if not title or not description:
            abort(400, description="Job title and description are required")
        db = get_db()
        with transaction(db):
            db.execute(
                """
                INSERT INTO jobs(employer_id, title, description, required_skills_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    g.user["id"],
                    title,
                    description,
                    skills_to_json(request.form.get("required_skills", "")),
                    iso_utc(utc_now()),
                ),
            )
        flash("Job created.", "success")
        return redirect(url_for("employer.dashboard"))
    return render_template("employer/job_form.html", job=None, skills="")


@bp.route("/jobs/<int:job_id>/edit", methods=("GET", "POST"))
@role_required("Employer")
def job_edit(job_id: int):
    job = _owned_job_or_error(job_id)
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        if not title or not description:
            abort(400, description="Job title and description are required")
        with transaction(get_db()):
            get_db().execute(
                """
                UPDATE jobs
                SET title = ?, description = ?, required_skills_json = ?
                WHERE id = ?
                """,
                (title, description, skills_to_json(request.form.get("required_skills", "")), job_id),
            )
        flash("Job updated.", "success")
        return redirect(url_for("employer.dashboard"))

    return render_template(
        "employer/job_form.html",
        job=job,
        skills=", ".join(skills_from_json(job["required_skills_json"])),
    )


@bp.post("/jobs/<int:job_id>/delete")
@role_required("Employer")
def job_delete(job_id: int):
    try:
        delete_job(get_db(), g.user["id"], job_id)
    except DomainError as exc:
        abort(exc.status_code, description=exc.message)
    flash("Job deleted.", "success")
    return redirect(url_for("employer.dashboard"))


@bp.get("/jobs/<int:job_id>/applicants")
@role_required("Employer")
def applicants(job_id: int):
    job = _owned_job_or_error(job_id)
    return render_template(
        "employer/applicants.html",
        job=job,
        applicants=rank_applicants(get_db(), job_id),
        statuses=VALID_STATUSES,
    )


@bp.post("/applications/<int:application_id>/status")
@role_required("Employer")
def application_status(application_id: int):
    try:
        update_application_status(
            get_db(),
            g.user["id"],
            application_id,
            request.form.get("status", ""),
        )
    except DomainError as exc:
        abort(exc.status_code, description=exc.message)
    flash("Application status updated.", "success")
    job_id = get_db().execute(
        "SELECT job_id FROM applications WHERE id = ?",
        (application_id,),
    ).fetchone()["job_id"]
    return redirect(url_for("employer.applicants", job_id=job_id))


@bp.post("/slots")
@role_required("Employer")
def slot_create():
    try:
        job_id = int(request.form.get("job_id", "0"))
        _owned_job_or_error(job_id)
        create_slot(
            get_db(),
            g.user["id"],
            job_id,
            parse_local_datetime(request.form.get("start_at", "")),
            parse_local_datetime(request.form.get("end_at", "")),
        )
    except (ValueError, DomainError) as exc:
        if isinstance(exc, DomainError):
            abort(exc.status_code, description=exc.message)
        abort(400, description="Invalid job ID")
    flash("Interview slot created.", "success")
    return redirect(url_for("employer.dashboard"))


@bp.post("/slots/<int:slot_id>/delete")
@role_required("Employer")
def slot_delete(slot_id: int):
    try:
        delete_slot(get_db(), g.user["id"], slot_id)
    except DomainError as exc:
        abort(exc.status_code, description=exc.message)
    flash("Interview slot deleted.", "success")
    return redirect(url_for("employer.dashboard"))
