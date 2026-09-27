from __future__ import annotations

from collections import deque
from threading import Lock
from time import monotonic

from flask import Flask, abort, request

from .db import get_db


WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def install_demo_guard(app: Flask) -> None:
    rate_state: dict[tuple[str, str], deque[float]] = {}
    rate_lock = Lock()

    @app.before_request
    def protect_public_demo():
        if not app.config["DEMO_MODE"]:
            return None

        if request.content_length and request.content_length > app.config["DEMO_MAX_REQUEST_BYTES"]:
            abort(413, description="Request body is too large for the public demo.")

        if request.method not in WRITE_METHODS:
            return None

        endpoint = request.endpoint or ""
        if endpoint == "auth.login":
            bucket = "login"
            limit = app.config["DEMO_LOGIN_PER_MINUTE"]
        elif endpoint == "auth.register":
            bucket = "register"
            limit = app.config["DEMO_REGISTER_PER_MINUTE"]
        else:
            bucket = "write"
            limit = app.config["DEMO_WRITE_PER_MINUTE"]

        client_ip = request.headers.get("CF-Connecting-IP") or request.remote_addr or "unknown"
        now = monotonic()

        # 公网 demo 只有一个容器进程，内存滑动窗口足以挡住常见脚本刷接口；
        # Cloudflare 会覆盖 CF-Connecting-IP，避免公网访客自己伪造来源 IP 绕过限流。
        with rate_lock:
            key = (bucket, client_ip)
            timestamps = rate_state.setdefault(key, deque())
            cutoff = now - 60
            while timestamps and timestamps[0] <= cutoff:
                timestamps.popleft()
            if len(timestamps) >= limit:
                abort(429, description="Too many requests. Please wait and try again.")
            timestamps.append(now)

            # 长时间运行时顺手清掉过期来源，避免大量不同 IP 让内存状态无限增长。
            if len(rate_state) > 4096:
                stale_keys = [
                    state_key
                    for state_key, values in rate_state.items()
                    if not values or values[-1] <= cutoff
                ]
                for state_key in stale_keys:
                    rate_state.pop(state_key, None)

        capacity = {
            "auth.register": ("users", app.config["DEMO_MAX_USERS"]),
            "employer.job_new": ("jobs", app.config["DEMO_MAX_JOBS"]),
            "candidate.apply": ("applications", app.config["DEMO_MAX_APPLICATIONS"]),
            "employer.slot_create": ("interview_slots", app.config["DEMO_MAX_SLOTS"]),
        }.get(endpoint)
        if capacity:
            table, maximum = capacity
            count = get_db().execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            if count >= maximum:
                abort(
                    429,
                    description="Public demo capacity reached. Ask the owner to reset the demo.",
                )

        return None
