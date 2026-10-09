#!/usr/bin/env bash
# Builds dist/romm-wsl.tar.gz, the rootfs RomM.ps1 imports with `wsl --import`.
#
# Usage: packaging/windows/build-rootfs.sh [romm image, default rommapp/romm:5.3.1]

set -o errexit
set -o nounset
set -o pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
ROMM_IMAGE="${1:-rommapp/romm:5.3.1}"
TAG=romm-wsl:build
DIST="${HERE}/dist"

mkdir -p "${DIST}"
docker build --platform linux/amd64 --build-arg ROMM_IMAGE="${ROMM_IMAGE}" -t "${TAG}" "${HERE}"

container=$(docker create --platform linux/amd64 "${TAG}")
trap 'docker rm -f "${container}" >/dev/null' EXIT
docker export "${container}" | gzip -6 >"${DIST}/romm-wsl.tar.gz"

size=$(du -h "${DIST}/romm-wsl.tar.gz")
echo "Wrote ${size}"
