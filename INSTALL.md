# Installation Guide

## Prerequisites and Versions

The graded project is tested with:

- Python 3.12.11
- pip bundled with Python 3.12.11 (the Docker base currently provides pip 25.0.1)
- Docker Engine/Desktop 29.7.2 or another Docker release compatible with the supplied Dockerfile
- Git 2.x for clean-checkout verification

Runtime/test packages are pinned in requirements.lock; direct installation goes through requirements.txt.

## Dependency Installation

From a clean checkout:

### Windows PowerShell

~~~powershell
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
~~~

### macOS/Linux

~~~bash
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
~~~

No Node.js, external database, API key, or hosted service is required.

## Environment Variables

The application reads these variables:

| Variable | Required | Meaning |
|---|---|---|
| SECRET_KEY | No for local demo; yes for any shared deployment | Flask session-signing secret |
| DATABASE_PATH | No | SQLite path. Default: Flask instance directory |
| PYTHONUNBUFFERED | No | Useful for container logs |

The application does not auto-load .env. Set environment variables in your shell/container explicitly.

## Database Setup and Migrations

The schema is defined in recruiting/schema.sql.

Initialize missing tables without deleting existing data:

~~~bash
flask --app recruiting init-db
~~~

This project has one current schema and no external migration framework. A clean grading checkout can initialize directly from schema.sql.

## Demo Data and Reset Command

The required deterministic reset-and-seed command is:

~~~bash
flask --app recruiting reset-seed
~~~

It drops only this application's local tables, recreates them, and inserts:

- four Candidate demo accounts;
- two Employer demo accounts;
- a Python/SQL job and an empty-requirements job;
- the required 100/50/0/100 match examples;
- applications covering Pending, Interviewing, Rejected, Accepted;
- Bob and Dave as two Interviewing candidates eligible for the same free slot;
- one historical booking retained on an Accepted application.

All demo accounts use DemoPass123!.

## Local Development

After seed:

~~~bash
python -m recruiting
~~~

Open http://127.0.0.1:8080.

Health check: http://127.0.0.1:8080/healthz

For a production-style local server instead of Flask's development server:

~~~bash
waitress-serve --call --listen=127.0.0.1:8080 recruiting:create_app
~~~

## Running Unit Tests

Run the complete student-written suite non-interactively:

~~~bash
python -m pytest -q
~~~

A failing test produces a nonzero exit code.

## Docker Build

From repository root:

~~~bash
docker build -t csc4801-teamzzz .
~~~

The Dockerfile contains the full Python environment and source code. No undocumented image is pulled at run time.

## Docker Startup

Start the application:

~~~bash
docker run -d --name csc4801-teamzzz -p 127.0.0.1:8080:8080 csc4801-teamzzz
~~~

Reset and seed the container database:

~~~bash
docker exec csc4801-teamzzz flask --app recruiting reset-seed
~~~

Run the full unit-test suite inside the same built environment:

~~~bash
docker exec csc4801-teamzzz python -m pytest -q
~~~

Smoke test:

~~~bash
curl http://127.0.0.1:8080/healthz
~~~

Expected response:

~~~json
{"ok":true}
~~~

Stop and remove:

~~~bash
docker rm -f csc4801-teamzzz
~~~

## Clean-Checkout Verification Before Submission

~~~bash
git clone https://github.com/Arvin-Chaser/CSC4801_TeamZzz.git
cd CSC4801_TeamZzz
git checkout main
docker build -t csc4801-teamzzz .
docker run -d --name csc4801-teamzzz -p 127.0.0.1:8080:8080 csc4801-teamzzz
docker exec csc4801-teamzzz flask --app recruiting reset-seed
docker exec csc4801-teamzzz python -m pytest -q
curl http://127.0.0.1:8080/healthz
~~~

Then complete the documented browser smoke flow with one Candidate and one Employer demo account.

## Troubleshooting

### ModuleNotFoundError: flask

Activate the intended virtual environment and rerun:

~~~bash
python -m pip install -r requirements.txt
~~~

### Database permission error

Set DATABASE_PATH to a writable absolute path. The Docker image already uses writable /data/recruiting.sqlite3.

### Port 8080 is already in use

Map another host port without changing the container:

~~~bash
docker run -d --name csc4801-teamzzz -p 127.0.0.1:8081:8080 csc4801-teamzzz
~~~

### Reset while testing

Tests never use the normal app database. They create isolated temporary SQLite files. It is safe to reset the demo database separately with flask --app recruiting reset-seed.

### Interview time confusion

The HTML form interprets timezone-less values as Asia/Shanghai. The database stores UTC ISO 8601 timestamps and the UI converts them back to Asia/Shanghai.
