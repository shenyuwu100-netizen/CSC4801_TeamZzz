# TalentMatch — CSC4801 Team Zzz

TalentMatch is a locally runnable full-stack recruiting and candidate-matching platform for CSC4801. Candidates maintain a private profile and resume, receive deterministic skill-overlap job recommendations, apply to jobs, and book interviews. Employers maintain a company profile, own job postings, rank applicants with the same score, update application status, and publish 30-minute interview availability.

Group name: **Zzz**

Project repository: https://github.com/shenyuwu100-netizen/CSC4801_TeamZzz

Live demo: https://csc4801.wushenyu.com

The public demo uses deterministic synthetic data, resets daily, and must not be used for real personal data. The graded artifact remains the GitHub commit and its reproducible Docker workflow.

## Architecture Summary

- Browser UI: server-rendered Jinja templates with automatic HTML escaping.
- Backend: Flask 3.1 application split into authentication, candidate, employer, matching, scheduling, and database modules.
- Database: SQLite relational database with foreign keys, checks, uniqueness constraints, and explicit transactions.
- Authentication: Flask session cookie plus Werkzeug scrypt password hashing.
- Matching: one shared deterministic implementation in recruiting/matching.py.
- Interview booking: BEGIN IMMEDIATE transaction plus unique database constraints on both application and slot.
- Deployment: one Dockerfile, Waitress WSGI server, writable /data database path.
- AI: no external LLM is required or called. FP-MATCH-2 is intentionally not implemented.

## Quick Start

See INSTALL.md for clean-checkout, local, and Docker instructions.

Fast local flow after installing dependencies:

~~~bash
flask --app recruiting reset-seed
python -m recruiting
~~~

Open http://127.0.0.1:8080.

## Demo Accounts

All seeded accounts use the local/demo password **DemoPass123!**.

| Role | Username | Purpose |
|---|---|---|
| Candidate | alice | Python + SQL; 100% match to Backend Engineer |
| Candidate | bob | Python; 50% match; Interviewing |
| Candidate | carol | Rust; 0% match |
| Candidate | dave | Go; second Interviewing candidate for booking conflict demo |
| Employer | acme | Owns Backend Engineer and shared race slot |
| Employer | beta | Owns Open Skills Role |

These credentials are intentionally non-production demo data.

## Running Unit Tests

~~~bash
python -m pytest -q
~~~

The complete suite is non-interactive and exits nonzero on failure. Regression tests include same-employer cross-job booking, deletion races using independent SQLite connections, and a synchronized two-client booking race. CI builds the image, starts it, seeds its isolated database, runs the suite inside it, and checks HTTP health.

## Requirement–Test Mapping

| Requirement ID | Behavior / evidence | Implementation file(s) | Unit test(s) / verification evidence |
|---|---|---|---|
| FP-ARCH-1 | Browser UI + backend rules + persistent relational DB | recruiting/, schema.sql, templates, Dockerfile | Clean local/Docker smoke flow in INSTALL.md |
| FP-AUTH-1 | Candidate/Employer registration, unique username, login/logout | recruiting/auth.py, recruiting/schema.sql | test_fp_auth_1_registration_and_session_lifecycle; test_fp_auth_1_invalid_registration |
| FP-AUTH-2 | Scrypt password hash; no password returned/rendered | recruiting/auth.py | test_fp_auth_2_salted_hash_and_password_verification |
| FP-AUTH-3 | Unauthenticated redirect, role/owner 403, allowed missing object 404 | auth decorators + candidate/employer routes | test_fp_auth_3_authorization_and_missing_object; test_fp_auth_3_ownership_precedes_status_validation; test_fp_auth_3_slot_owner_precedes_date_validation; security/workflow ownership tests |
| FP-CAN-1 | Own profile/skills and private raw-text resume | recruiting/candidate.py, matching.py | test_fp_can_1_profile_and_private_resume_rules |
| FP-CAN-2 | All jobs ranked by required score with required display fields | candidate.dashboard, rank_jobs | test_fp_can_2_recommendations_preserve_fields_and_rank_all_jobs |
| FP-CAN-3 | Single Pending application; own application views only | candidate.apply, application routes, DB unique constraint | test_fp_can_3_pending_duplicate_and_application_owner |
| FP-EMP-1 | Own company name/description editing | recruiting/employer.py | test_fp_emp_1_company_profile |
| FP-EMP-2 | Own job CRUD, validation, ownership, 409 dependent deletion | employer routes + services.delete_job | test_fp_emp_2_job_validation_and_deletion; test_fp_emp_2_application_wins_against_job_deletion |
| FP-EMP-3 | Ranked applicant fields + exact status transitions + role ownership | rank_applicants, employer status route | test_fp_emp_3_applicant_fields_order_status_and_role |
| FP-MATCH-1 | Normalized skill-overlap formula and both tie-break contracts | recruiting/matching.py | test_fp_match_1_examples_normalization_and_floor; test_fp_match_1_both_tie_breakers; test_fp_match_1_lowercase_does_not_merge_distinct_unicode_skills |
| FP-MATCH-2 | Optional LLM enhancement | N/A | N/A — deliberately not implemented |
| FP-SCHED-1 | Future exact 30-minute employer-owned slots with a source job; booked slot cannot delete | services.create_slot, delete_slot | test_fp_sched_1_slot_creation_timezones_and_deletion; test_fp_sched_1_invalid_slots; test_fp_sched_1_booking_wins_against_slot_deletion |
| FP-SCHED-2 | Ownership, same employer across jobs, Interviewing, future, free slot, one booking, visibility | services.book_slot, candidate/employer views | test_fp_sched_2_eligible_booking; test_fp_sched_2_ineligible_booking; test_fp_sched_2_booking_is_visible_and_booked_slot_is_hidden; test_fp_sched_2_same_employer_different_job_is_eligible; test_fp_sched_2_same_employer_cross_job_service; test_fp_sched_2_ineligible_status_leaves_database_unchanged; test_fp_sched_2_expired_slot_leaves_database_unchanged |
| FP-SCHED-3 | Atomic booking conflict; exactly one booking; exact conflict message | services.book_slot, unique DB constraints | test_fp_sched_3_conflict_contract; test_fp_sched_3_independent_connections_have_one_winner; BEGIN IMMEDIATE and unique constraints |
| FP-SEC-1 | Representative direct-object authorization boundaries | auth decorators + candidate/employer/service checks | test_fp_sec_1_object_access_boundaries plus CAN/EMP tests |
| FP-SEC-2 | Bound SQL parameters for user-controlled values | all database modules, services.search_jobs | test_fp_sec_2_sql_metacharacters_are_bound |
| FP-SEC-3 | Jinja autoescape for profile/resume/company/job/search text | all templates; no safe rendering | test_fp_sec_3_xss_is_escaped |
| FP-SEC-4 | No real secrets/personal data; isolated temp test DB; no third-party test calls | .env.example, .gitignore, pytest fixtures | test_fp_sec_4_secrets_and_test_isolation |
| FP-PROC-1 | Living architecture/data/auth/routes/UI/matching/booking/security spec | SPEC.md | Document review against graded commit |
| FP-DOC-1 | Exact prerequisites/install/env/DB/seed/run/test/Docker/troubleshooting | INSTALL.md | Clean-checkout verification |
| FP-DOC-2 | Overview, architecture, demo accounts, test command, docs, mapping, limitations | README.md | Document review |
| FP-DOC-3 | Deterministic reset+seed with required actors/examples/statuses/race fixture | recruiting/seed.py, CLI command | Seed data exercised across unit suite |
| FP-TEST-1 | Student-written unit tests for every functional requirement plus required security/conflict cases | tests/unit/ | python -m pytest -q |
| FP-SUB-1 | Permanent main-branch commit URL + Docker-buildable graded commit | Dockerfile, INSTALL.md, repository main branch | Final submission uses exact 40-character commit URL after grading commit is pushed |

## Document Index

- REQUIREMENTS.md — normative course requirements.
- SPEC.md — living implementation specification.
- INSTALL.md — clean setup, seed, run, test, and Docker commands.
- PEER_REVIEW.md — course peer-audit procedure.
- DOCKER.md — course Docker expectations.
- TEAM_GUIDE.md — code tour and common safe modifications.
- deploy/demo/README.md — isolated public-demo deployment and safety model.
- .github/ISSUE_TEMPLATE/audit_bug_report.yml — required audit issue form.
- .github/labels.yml — required audit label definitions.

## Known Limitations

- PDF resume upload/extraction is not implemented; the required raw-text resume workflow is complete.
- FP-MATCH-2 optional LLM explanations are not implemented; the application has no external AI/service dependency.
- Existing skills previously collapsed by Unicode case folding cannot be reconstructed automatically; re-enter affected profiles or job skills if needed. New edits follow the exact lowercase contract.
- User-entered interview times are interpreted as Asia/Shanghai and stored in UTC.
- SQLite is selected deliberately for reproducible local grading. The booking transaction uses SQLite write serialization plus unique constraints; production-scale deployments would normally use a server database.
- The final permanent GitHub commit URL is created only when the team freezes and pushes the graded commit to main.
