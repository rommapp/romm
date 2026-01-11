#!/bin/sh

set -eu

DATA_DIR="${VALKEY_DATA_DIR:-/data}"
ACL_FILE="${VALKEY_ACL_FILE:-$DATA_DIR/users.acl}"

# Required secrets
# - SFU password must be explicit.
# - RomM password defaults to ROMM_AUTH_SECRET_KEY (optional override: VALKEY_ROMM_PASSWORD).
: "${VALKEY_SFU_PASSWORD:?set VALKEY_SFU_PASSWORD}"

VALKEY_ROMM_PASSWORD="${VALKEY_ROMM_PASSWORD:-${ROMM_AUTH_SECRET_KEY:-}}"
if [ -z "${VALKEY_ROMM_PASSWORD}" ]; then
  echo "ERROR: set ROMM_AUTH_SECRET_KEY (or VALKEY_ROMM_PASSWORD) for the 'romm' ACL user" >&2
  exit 1
fi

mkdir -p "$(dirname "$ACL_FILE")"

regenerate_acl=false
if [ -f "$ACL_FILE" ]; then
  # Valkey is strict about ACL file contents. Keep it to only `user ...` lines.
  if grep -qvE '^user[[:space:]]+[^[:space:]]+' "$ACL_FILE"; then
    echo "WARN: Detected invalid lines in ACL file; regenerating: $ACL_FILE" >&2
    rm -f "$ACL_FILE" || true
    regenerate_acl=true
  fi
else
  regenerate_acl=true
fi

if [ "$regenerate_acl" = true ]; then
  umask 077
  cat >"$ACL_FILE" <<EOF
user default off
user romm on >$VALKEY_ROMM_PASSWORD ~* &* +@all
user sfu on >$VALKEY_SFU_PASSWORD ~sfu:* &* -@all +ping +get +set +setnx +del +exists +expire +ttl +pttl +hget +hgetall +hexists +eval +evalsha
EOF
  chmod 600 "$ACL_FILE" || true
fi

exec valkey-server \
  --dir "$DATA_DIR" \
  --bind 0.0.0.0 \
  --protected-mode yes \
  --aclfile "$ACL_FILE"
