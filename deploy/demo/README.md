# Public demo deployment

The public course demo is hosted at:

https://csc4801.wushenyu.com

This deployment is intentionally separate from the development/test database.

## Safety model

- Docker only publishes the origin on `127.0.0.1:18084`.
- Cloudflare Tunnel is the only public ingress.
- Public HTTP requests are redirected to HTTPS; demo session cookies are Secure, HttpOnly, and SameSite=Lax.
- The demo uses a dedicated Docker volume.
- Container startup runs `reset-seed`, so a restart always restores deterministic synthetic data.
- The Windows deployment host also runs a daily reset task.
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

The host scripts under `deploy/windows/` are used by Windows Task Scheduler to recover the service after login and reset demo data daily.

## Manual reset

```powershell
.\deploy\windows\reset-demo.ps1
```

The reset affects only the isolated public demo database.

If a deployment-only fixed demo account is configured, the reset command recreates it immediately after restoring the deterministic course seed.
