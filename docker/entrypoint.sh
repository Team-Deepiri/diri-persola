#!/bin/sh
set -e

# Optional migrate-on-boot for compose/prod (set PERSOLA_AUTO_MIGRATE=1).
if [ "${PERSOLA_AUTO_MIGRATE:-0}" = "1" ] && [ -d /app/alembic ]; then
  echo "[persola] running alembic upgrade head"
  cd /app
  if [ -f /app/alembic/alembic.ini ]; then
    poetry run alembic -c /app/alembic/alembic.ini upgrade head \
      || python -m alembic -c /app/alembic/alembic.ini upgrade head \
      || true
  fi
fi

exec "$@"
