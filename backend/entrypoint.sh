#!/bin/sh
# API container entrypoint: wait for Postgres, migrate, seed (if available), run dev server.
set -e

echo "[entrypoint] waiting for database..."
python - <<'PY'
import os, sys, time
import dj_database_url, psycopg

cfg = dj_database_url.parse(os.environ["DATABASE_URL"])
for attempt in range(60):
    try:
        psycopg.connect(
            host=cfg["HOST"], port=cfg["PORT"] or 5432, user=cfg["USER"],
            password=cfg["PASSWORD"], dbname=cfg["NAME"], connect_timeout=3,
        ).close()
        print("[entrypoint] database is up")
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"[entrypoint] database not ready ({exc.__class__.__name__}); retrying")
        time.sleep(1)
sys.exit("[entrypoint] database never became available")
PY

python manage.py migrate --noinput

if python manage.py help seed_demo >/dev/null 2>&1; then
  echo "[entrypoint] running seed_demo"
  python manage.py seed_demo
else
  echo "[entrypoint] seed_demo command not available yet; skipping"
fi

exec python manage.py runserver 0.0.0.0:8000
