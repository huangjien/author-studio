#!/bin/sh
set -eu

# Defaults
DATA_DIR=${DATA_DIR:-/app/.data}
KEY_FILE_DEFAULT="$DATA_DIR/api_keys.txt"
KEY_FILE=${API_KEYS_FILE:-$KEY_FILE_DEFAULT}

mkdir -p "$DATA_DIR"

# If API_KEY provided by the operator, prefer it and persist into KEY_FILE (append if missing)
if [ -n "${API_KEY:-}" ]; then
  echo "[startup] Using provided API_KEY from environment"
  if [ -n "$KEY_FILE" ]; then
    touch "$KEY_FILE"
    chmod 600 "$KEY_FILE" || true
    if ! grep -qxF "$API_KEY" "$KEY_FILE" 2>/dev/null; then
      echo "$API_KEY" >> "$KEY_FILE"
    fi
  fi
else
  # No API_KEY set; try to load from KEY_FILE, otherwise generate and persist
  if [ -f "$KEY_FILE" ] && [ -s "$KEY_FILE" ]; then
    GENERATED_KEY=$(head -n1 "$KEY_FILE")
    export API_KEY="$GENERATED_KEY"
    echo "[startup] Loaded persisted API_KEY from $KEY_FILE"
    echo "[startup] API_KEY: $GENERATED_KEY"
  else
    # Generate a secure random key via Python
    GENERATED_KEY=$(python - <<'PY'
import secrets
print(secrets.token_urlsafe(32))
PY
)
    export API_KEY="$GENERATED_KEY"
    mkdir -p "$(dirname "$KEY_FILE")"
    printf "%s\n" "$GENERATED_KEY" > "$KEY_FILE"
    chmod 600 "$KEY_FILE" || true
    echo "[startup] Generated API_KEY and saved to $KEY_FILE"
    echo "[startup] API_KEY: $GENERATED_KEY"
  fi
fi

# Ensure API_KEYS_FILE is exported for the app to support file-based keys
export API_KEYS_FILE="$KEY_FILE"

# Show paths for admin visibility
echo "[startup] DATA_DIR: $DATA_DIR"
echo "[startup] API_KEYS_FILE: $API_KEYS_FILE"

echo "[startup] Starting FastAPI (uvicorn) on 0.0.0.0:8000"
exec uvicorn src.main:app --host 0.0.0.0 --port 8000
