#!/usr/bin/env bash
# Installs the pinned toolchain (uv, Python, Node, Trunk) and the project
# dependencies. Safe to re-run: each step is skipped when already satisfied.
#
# Usage: scripts/dev-setup.sh [--db]
#   --db  also install and start a local MariaDB with the pytest database
#         (Debian/Ubuntu only).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOCAL_BIN="${HOME}/.local/bin"
export PATH="${LOCAL_BIN}:${PATH}:/usr/sbin:/sbin"

with_db=false
for arg in "$@"; do
	case "${arg}" in
	--db) with_db=true ;;
	*)
		echo "unknown option: ${arg}" >&2
		exit 2
		;;
	esac
done

log() { printf '==> %s\n' "$*"; }

as_root() {
	if [[ ${EUID} -eq 0 ]]; then "$@"; else sudo "$@"; fi
}

apt_install() {
	local missing=() pkg
	for pkg in "$@"; do
		dpkg-query -W -f='${Status}' "${pkg}" 2>/dev/null | grep -q "ok installed" ||
			missing+=("${pkg}")
	done
	[[ ${#missing[@]} -eq 0 ]] && return 0
	if ! command -v apt-get >/dev/null; then
		log "Skipping ${missing[*]}: install them with your package manager"
		return 0
	fi
	log "Installing ${missing[*]}"
	as_root apt-get update -qq >/dev/null
	as_root env DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "${missing[@]}" >/dev/null
}

setup_uv() {
	local want have
	want="$(sed -n 's/^ARG UV_VERSION=//p' "${ROOT}/docker/Dockerfile")"
	have="$(uv --version 2>/dev/null || true)"
	have="${have#uv }"
	have="${have%% *}"
	if [[ ${have} == "${want}" ]]; then return 0; fi
	log "Installing uv ${want} (found ${have:-none})"
	curl -LsSf "https://astral.sh/uv/${want}/install.sh" |
		env UV_UNMANAGED_INSTALL="${LOCAL_BIN}" sh >/dev/null
	hash -r
}

setup_backend() {
	# Build headers for the mariadb and psycopg[c] drivers.
	apt_install libmariadb-dev libpq-dev
	log "Syncing backend dependencies"
	(cd "${ROOT}" && uv python install --quiet && uv sync --frozen --all-extras --dev --quiet)
}

setup_node() {
	local want have full os arch dest
	want="$(tr -d '[:space:]' <"${ROOT}/frontend/.nvmrc")"
	have="$(node --version 2>/dev/null || true)"
	if [[ ${have} == "v${want}."* ]]; then return 0; fi
	full="$(curl -fsSL https://nodejs.org/dist/index.json | grep -o "\"v${want}\.[0-9]*\"" | head -1 | tr -d '"')"
	os="$(uname -s | tr '[:upper:]' '[:lower:]')"
	arch="$(uname -m)"
	case "${arch}" in
	x86_64) arch=x64 ;;
	aarch64) arch=arm64 ;;
	*) ;;
	esac
	dest="${HOME}/.local/share/node/${full}"
	log "Installing Node ${full} (found ${have:-none})"
	mkdir -p "${dest}" "${LOCAL_BIN}"
	curl -fsSL "https://nodejs.org/dist/${full}/node-${full}-${os}-${arch}.tar.xz" |
		tar -xJ -C "${dest}" --strip-components=1
	ln -sf "${dest}/bin/node" "${dest}/bin/npm" "${dest}/bin/npx" "${LOCAL_BIN}/"
	hash -r
}

setup_frontend() {
	local stamp="${ROOT}/frontend/node_modules/.dev-setup-stamp" node_version lock_sum
	node_version="$(node --version)"
	lock_sum="$(cksum <"${ROOT}/frontend/package-lock.json")"
	if [[ -f ${stamp} && "$(<"${stamp}")" == "${node_version} ${lock_sum}" ]]; then return 0; fi
	log "Installing frontend dependencies"
	(cd "${ROOT}/frontend" && npm ci --no-audit --no-fund --no-update-notifier --loglevel=error)
	echo "${node_version} ${lock_sum}" >"${stamp}"
}

setup_trunk() {
	command -v trunk >/dev/null && return 0
	log "Installing Trunk and its linters"
	curl -fsSL https://get.trunk.io | as_root bash -s -- -y >/dev/null
	(cd "${ROOT}" && trunk install --ci >/dev/null 2>&1) ||
		log "Trunk could not download its linters (network policy?); trunk check will retry on first use"
}

setup_db() {
	apt_install mariadb-server
	if ! mariadb-admin ping --silent >/dev/null 2>&1; then
		log "Starting MariaDB"
		as_root service mariadb start >/dev/null
	fi
	as_root mariadb <"${ROOT}/backend/romm_test/setup.sql"
}

setup_uv
setup_backend
setup_node
setup_frontend
setup_trunk
if [[ ${with_db} == true ]]; then setup_db; fi

uv_version="$(uv --version)"
python_version="$(cd "${ROOT}" && uv run --quiet python --version)"
node_version="$(node --version)"
log "Toolchain ready: ${uv_version%% (*}, ${python_version}, Node ${node_version}"
