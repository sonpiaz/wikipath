#!/bin/sh
set -e

# Seed the DuckDB file onto the volume on first boot. The volume mount
# at /data persists across deploys, so this only runs the very first
# time the volume is empty. Subsequent deploys keep whatever the API
# (and operator) wrote to /data/wikipath.duckdb.
if [ ! -f /data/wikipath.duckdb ]; then
  echo "[entrypoint] seeding /data/wikipath.duckdb from image"
  cp /app/seed.duckdb /data/wikipath.duckdb
fi

exec /app/wikipath-api -db /data/wikipath.duckdb -addr :8080
