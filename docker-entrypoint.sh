#!/bin/sh
set -e

# Seed the DuckDB file onto the volume. Tracks seed hash on the volume so
# code-only redeploys preserve any events the API has captured, but data
# updates (new seed.duckdb baked into the image) trigger an automatic
# re-sync. Lose events only when the underlying data actually changes —
# acceptable for v0.x where event volume is minimal.
SEED=/app/seed.duckdb
VOL=/data/wikipath.duckdb
HASHFILE=/data/.seed_hash

SEED_HASH=$(md5sum "$SEED" | awk '{print $1}')
PREV_HASH=""
[ -f "$HASHFILE" ] && PREV_HASH=$(cat "$HASHFILE")

if [ ! -f "$VOL" ]; then
  echo "[entrypoint] volume empty, seeding from image"
  cp "$SEED" "$VOL"
  echo "$SEED_HASH" > "$HASHFILE"
elif [ "$SEED_HASH" != "$PREV_HASH" ]; then
  echo "[entrypoint] seed hash changed (was: ${PREV_HASH:-empty}, now: ${SEED_HASH}), re-seeding"
  cp "$SEED" "$VOL"
  echo "$SEED_HASH" > "$HASHFILE"
else
  echo "[entrypoint] seed unchanged, keeping volume DB"
fi

exec /app/wikipath-api -db "$VOL" -addr :8080
