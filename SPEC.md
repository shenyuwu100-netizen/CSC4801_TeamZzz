# TalentMatch Project Specification

## Product Scope

TalentMatch is the fixed CSC4801 recruiting and candidate-matching product. It supports exactly two application roles: **Candidate** and **Employer**. The core application runs locally without any paid credential or third-party service.

Candidates can maintain their own profile and raw-text resume, see every current job ranked by a deterministic match score, submit one application per job, inspect their own statuses, and book eligible interview slots.

Employers can maintain a company profile, manage only their own jobs, see applicants for those jobs ranked with the same score, update the four allowed application statuses, and manage job-specific interview availability.

## Architecture

The application uses a server-rendered Flask architecture:

~~~text
Browser
  |  HTTP + session cookie
  v
Flask routes
  +-- auth.py       registration, login/logout, role decorators
  +-- candidate.py  candidate profile/resume/jobs/applications/booking
  +-- employer.py   company/jobs/applicants/status/availability
  +-- matching.py   one deterministic matching implementation
  +-- services.py   scheduling, booking, status and deletion business rules
  +-- db.py         SQLite connection, schema lifecycle, explicit transactions
          |
          v
      SQLite DB
~~~

Jinja templates are the browser UI. Business rules remain on the server even when the UI hides unavailable actions.

## Data Model and Relationships

~~~text
users
 +-- 1:1 candidate_profiles
 +-- 1:1 company_profiles

users(Employer) 1 --- * jobs
users(Candidate) 1 -- * applications * -- 1 jobs
jobs 1 ------------- * interview_slots
applications 1 ----- 0..1 bookings 0..1 ----- 1 interview_slots
~~~

### Tables

- users(id, username, password_hash, role, created_at)
  - username unique.
  - role database check: only Candidate or Employer.
- candidate_profiles(user_id, display_name, skills_json, resume_text)
  - user_id is the owning Candidate.
  - skills_json stores a JSON array of cleaned display skill strings.
  - resume_text is private raw text.
- company_profiles(user_id, company_name, description)
  - one profile per Employer.
- jobs(id, employer_id, title, description, required_skills_json, created_at)
  - required skills use the same JSON-list representation.
- applications(id, candidate_id, job_id, status, created_at)
  - unique (candidate_id, job_id).
  - status check allows exactly Pending, Interviewing, Rejected, Accepted.
- interview_slots(id, job_id, employer_id, start_at, end_at)
  - exact UTC ISO timestamps; each slot belongs to one owned job.
- bookings(id, application_id, slot_id, booked_at)
  - unique application_id enforces at most one booking per application.
  - unique slot_id enforces at most one application per slot.

Foreign keys are enabled on every connection.

## Authentication and Authorization

Passwords are generated with Werkzeug's established scrypt password hashing. Password hashes never leave backend/database logic.

After login, the session stores only the user ID. A before-request hook reloads id, username, and role from the database.

Protected routes use role_required("Candidate") or role_required("Employer"):

- missing session -> redirect to login;
- authenticated wrong role/owner -> 403;
- absent object that the caller would otherwise be allowed to access -> 404.

Object ownership is rechecked in backend queries/services. The UI is not considered an authorization boundary.

## API Routes or Server Actions

### Public

| Method | Path | Purpose |
|---|---|---|
| GET | / | Product landing page |
| GET/POST | /auth/register | Register Candidate or Employer |
| GET/POST | /auth/login | Login |
| GET | /healthz | Local/container health check |

### Authenticated common

| Method | Path | Purpose |
|---|---|---|
| POST | /auth/logout | End session |

### Candidate

| Method | Path | Purpose |
|---|---|---|
| GET | /candidate/ | All jobs ranked by match score |
| GET | /candidate/search?q=... | Parameterized job/company text search |
| GET/POST | /candidate/profile | Own display name and skills |
| GET/POST | /candidate/resume/<candidate_id> | Own private raw-text resume; other IDs forbidden |
| GET | /candidate/jobs/<job_id> | Job detail |
| POST | /candidate/jobs/<job_id>/apply | Create one Pending application |
| GET | /candidate/applications | Own applications |
| GET | /candidate/applications/<id> | Own application + booking options |
| POST | /candidate/applications/<id>/book/<slot_id> | Atomic booking |

### Employer

| Method | Path | Purpose |
|---|---|---|
| GET | /employer/ | Own jobs and availability |
| GET/POST | /employer/company | Own company profile |
| GET/POST | /employer/jobs/new | Create job |
| GET/POST | /employer/jobs/<id>/edit | Edit owned job |
| POST | /employer/jobs/<id>/delete | Delete owned dependency-free job |
| GET | /employer/jobs/<id>/applicants | Ranked applicants for owned job |
| POST | /employer/applications/<id>/status | Set exact allowed status |
| POST | /employer/slots | Create future 30-minute slot |
| POST | /employer/slots/<id>/delete | Delete owned unbooked slot |

## User Interface and Workflows

### Candidate screens

1. Dashboard shows every current job with score, title, company, required skills, description summary, and detail link.
2. Profile edits display name and technical skills.
3. Resume stores/replaces private raw text.
4. Job detail submits one application.
5. Applications list shows job, employer, status, and booking.
6. Application detail lists free future slots only while status is Interviewing.
7. Search is separate from the all-jobs dashboard, so the required dashboard remains complete.

### Employer screens

1. Dashboard shows owned jobs, counts, slot state, and slot creation.
2. Company profile edits name/description.
3. Job form creates/edits required title, description, and optional skill list.
4. Applicants screen shows candidate identity, skills, score, status, and booking, with status update controls.

## Matching Algorithm and Skill Storage

The canonical implementation is recruiting/matching.py::skill_match_score.

Skill input is split on commas, semicolons, or newlines, trimmed, empty values removed, and duplicates removed case-insensitively. Cleaned display strings are stored as JSON arrays. The score again normalizes to lowercase/casefold sets so storage formatting never changes the contract.

Let C be normalized candidate skills and R normalized required skills:

~~~text
score = 100                                      when |R| = 0
score = floor(100 * |C intersection R| / |R|)   otherwise
~~~

Candidate ranking uses descending score, then case-insensitive job title, then job ID. Employer applicant ranking uses descending score, then case-insensitive candidate display name, then candidate ID. Both views call the same score implementation.

Resume text is never an input to the required score.

## Interview Scheduling and Booking Transaction

Form times are interpreted in **Asia/Shanghai** unless they already carry an explicit offset. All stored timestamps are UTC ISO 8601 strings.

Slot creation validates:

- owning employer owns the selected job;
- both times are timezone-aware after parsing;
- end is after start;
- duration is exactly 30 minutes;
- start is in the future.

services.book_slot executes an explicit SQLite BEGIN IMMEDIATE transaction. Inside the transaction it checks:

1. application exists;
2. candidate owns the application;
3. slot exists and belongs to the same job/employer;
4. status is Interviewing;
5. slot remains in the future;
6. application has no booking;
7. slot has no booking.

The insert is additionally protected by UNIQUE(application_id) and UNIQUE(slot_id) in the database. Thus competing writers cannot both commit the same slot. A losing attempt returns HTTP 409 / domain conflict with the exact message **Slot already booked**. If an application later leaves Interviewing, status update does not touch its booking.

## Security Controls

### Object authorization

Server-side role and ownership checks protect resume/application/job/applicant/slot operations. Direct ID changes are tested.

### SQL injection

All user-controlled SQL values are passed through SQLite parameter placeholders (?). No route builds SQL by concatenating raw user input. Search uses three bound LIKE parameters.

### XSS

Jinja autoescaping remains enabled. User-controlled profile, resume, company, job, and search content is rendered with normal expressions. No template disables escaping for user input.

### Passwords and session

Passwords use scrypt hashes. The session cookie is HttpOnly and SameSite=Lax. SECRET_KEY is configurable by environment; repository values are demo placeholders only.

### Secrets and test isolation

The repository contains no real API key or production data. .env and SQLite files are ignored. Pytest creates a fresh temporary SQLite database per test app and makes no third-party network calls.

## Optional AI Features and Data Flow

**Not implemented (FP-MATCH-2 = N/A).** No resume, profile, company, or job text is sent to an LLM. The project therefore has no prompt, model credential, external AI data flow, or paid-service dependency.

## Design Decisions and Limitations

- SQLite was selected for clean local grading and deterministic setup. BEGIN IMMEDIATE plus uniqueness constraints provide the required atomic slot winner contract.
- Jobs are hard-deleted only when no application or interview slot depends on them.
- Raw-text resume is implemented; PDF extraction is optional and omitted.
- The application intentionally stays server-rendered rather than adding a JavaScript SPA layer that would duplicate authorization/business logic.
