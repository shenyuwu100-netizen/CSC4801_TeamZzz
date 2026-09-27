# Public demo deployment

The public course demo is hosted at:

https://csc4801.wushenyu.com

This deployment is intentionally separate from the development/test database.

## Safety model

- Docker only publishes the origin on `127.0.0.1:18084`.
- Cloudflare Tunnel is the only public ingress.
- Public HTTP requests are redirected to HTTPS; demo session cookies are Secure, HttpOnly, and SameSite=Lax.
- The demo uses a dedicated Docker volume.
- Container startup preserves the existing demo database; a fresh empty volume is seeded once.
- Demo data is reset only when `reset-demo.ps1` is run manually (for example before a presentation).
- The container runs without Linux capabilities, with `no-new-privileges`, a read-only root filesystem, and basic CPU/memory/PID limits.
- The live site is demonstration-only. Do not enter real personal data.

## Deployment host setup

Create the untracked environment file:

```powershell
Copy-Item deploy\demo\.env.example deploy\demo\.env
```

Replace `DEMO_SECRET_KEY` with a random secret, then:

- optionally set `DEMO_PERSONAL_USERNAME` and `DEMO_PERSONAL_PASSWORD` for one deployment-only fixed demo account;
- keep those values only in the untracked `.env` file; they are intentionally not committed to GitHub;
- `DEMO_PERSONAL_ROLE` defaults to `Candidate`.

```powershell
docker compose -f deploy\demo\docker-compose.yml --env-file deploy\demo\.env up -d --build
```

Local origin health:

```text
http://127.0.0.1:18084/healthz
```

The host startup script is used by Windows Task Scheduler to recover the service after login. The reset script is intentionally manual so normal use survives restarts.

## Abuse protection

The public demo adds deployment-only guard rails without changing the normal coursework behavior:

- login: 20 POST attempts per minute per client IP;
- registration: 8 POST attempts per minute per client IP;
- other write operations: 60 per minute per client IP;
- maximum request body: 64 KiB;
- capacity limits: 100 users, 300 jobs, 2,000 applications, and 1,000 interview slots.

When a limit is reached the demo returns HTTP 429. These limits apply only in `DEMO_MODE`; local/coursework runs are unaffected. Cloudflare Tunnel remains the only public ingress, so the origin port is not exposed directly.

## Manual reset

```powershell
.\deploy\windows\reset-demo.ps1
```

The reset affects only the isolated public demo database.

If a deployment-only fixed demo account is configured, the reset command recreates it immediately after restoring the deterministic course seed.
