# Team Zzz Code Tour

Every team member is responsible for understanding and safely modifying the graded code. This page is a short orientation, not a substitute for reading the source.

## Where to Start

1. Read REQUIREMENTS.md.
2. Read SPEC.md for the implementation contract.
3. Run flask --app recruiting reset-seed.
4. Run python -m pytest -q.
5. Start python -m recruiting and use both a Candidate and Employer demo account.

## Main Modules

- recruiting/auth.py: sessions, registration, login/logout, role decorators.
- recruiting/candidate.py: candidate profile/resume/recommendation/application/booking routes.
- recruiting/employer.py: company/job/applicant/status/slot routes.
- recruiting/matching.py: canonical skill parser and score/ranking functions.
- recruiting/services.py: business rules whose error outcomes must stay stable, especially booking.
- recruiting/db.py: SQLite connection, transactions, schema/reset commands.
- recruiting/schema.sql: relational constraints.
- recruiting/seed.py: deterministic demo fixture.
- tests/unit/: requirement-level regression tests.

## Safe Common Changes

### Add a candidate/employer field

Update schema, the matching profile/company route, template, seed if demo-visible, SPEC, and a unit test. Do not expose another candidate's private data.

### Change matching

Do not create a second scoring implementation. Modify skill_match_score only, preserve the required formula, and rerun both matching and workflow tests.

### Change interview booking

Treat book_slot as a transaction boundary. Preserve BEGIN IMMEDIATE, database unique constraints, the eligibility checks, and the exact conflict text Slot already booked.

### Add a route

Decide whether it is public, Candidate-only, or Employer-only. Add the relevant decorator and object-ownership check before mutation/read. Test 403/404 behavior where applicable.

## Before Pushing to main

~~~bash
python -m pytest -q
docker build -t csc4801-teamzzz .
~~~

Then verify README.md requirement mapping and SPEC.md still describe the actual code.
