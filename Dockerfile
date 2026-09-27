FROM python:3.12.11-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    DATABASE_PATH=/data/recruiting.sqlite3

WORKDIR /app

COPY requirements.lock requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt

RUN useradd --create-home --uid 10001 student \
    && mkdir -p /data \
    && chown -R student:student /data /app

COPY --chown=student:student . .

USER student
EXPOSE 8080

CMD ["waitress-serve", "--call", "--listen=0.0.0.0:8080", "recruiting:create_app"]
