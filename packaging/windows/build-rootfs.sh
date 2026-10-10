#!/usr/bin/env bash
# Builds the Windows release pair into dist/: romm-wsl-<version>.tar.gz, the
# rootfs `wsl --import` takes, and RomM-<version>.ps1, stamped to default to it.
#
# Usage: packaging/windows/build-rootfs.sh [romm image] [version]
#   romm image  default rommapp/romm:5.3.1; a digest reference works too
#   version     default dev

set -o errexit
set -o nounset
set -o pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROMM_IMAGE="${1:-rommapp/romm:5.3.1}"
VERSION="${2:-dev}"
TAG=romm-wsl:build
DIST="${HERE}/dist"
ROOTFS="${DIST}/romm-wsl-${VERSION}.tar.gz"
SCRIPT="${DIST}/RomM-${VERSION}.ps1"

if [[ ! ${VERSION} =~ ^[0-9A-Za-z.-]+$ ]]; then
	echo "Invalid version: ${VERSION}" >&2
	exit 1
fi

mkdir -p "${DIST}"
docker build --platform linux/amd64 \
	--build-arg ROMM_IMAGE="${ROMM_IMAGE}" --build-arg ROMM_VERSION="${VERSION}" \
	-t "${TAG}" "${HERE}"

container=$(docker create --platform linux/amd64 "${TAG}")
trap 'docker rm -f "${container}" >/dev/null' EXIT
docker export "${container}" | gzip -6 >"${ROOTFS}"

sed "s/^\$RommVersion = 'dev'\$/\$RommVersion = '${VERSION}'/" "${HERE}/RomM.ps1" >"${SCRIPT}"
if ! grep -qxF "\$RommVersion = '${VERSION}'" "${SCRIPT}"; then
	echo "Failed to stamp the version into ${SCRIPT}" >&2
	exit 1
fi

du -h "${ROOTFS}" "${SCRIPT}"
