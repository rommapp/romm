#!/bin/bash
# SessionStart hook for cloud sessions: runs dev-setup.sh, which also restarts
# MariaDB since environment snapshots keep files but not running processes.

if [[ ${CLAUDE_CODE_REMOTE-} != "true" ]]; then
	exit 0
fi

if [[ -n ${CLAUDE_ENV_FILE-} ]]; then
	echo "export PATH=\"${HOME}/.local/bin:\$PATH\"" >>"${CLAUDE_ENV_FILE}"
fi

LOG="${TMPDIR:-/tmp}/romm-dev-setup.log"
if bash "${CLAUDE_PROJECT_DIR}/scripts/dev-setup.sh" --db >"${LOG}" 2>&1; then
	tail -n 1 "${LOG}"
else
	echo "scripts/dev-setup.sh --db failed; see ${LOG}"
fi
