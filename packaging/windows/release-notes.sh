#!/usr/bin/env bash
# Merges the Windows install section into a release body: reads the body on
# stdin and prints it with any earlier section replaced by a freshly rendered one.
#
# Usage: release-notes.sh <version> <RomM-*.ps1> <romm-wsl-*.tar.gz> <body.md

set -o errexit
set -o nounset
set -o pipefail

HERE=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
VERSION="$1"
PS1_SHA256=$(sha256sum "$2" | cut -d' ' -f1)
ROOTFS_SHA256=$(sha256sum "$3" | cut -d' ' -f1)

# Drop the previous section, then trailing blank lines, so reruns don't stack.
body=$(awk '
	/^<!-- romm-windows:start -->\r?$/ { skip = 1 }
	!skip { print }
	/^<!-- romm-windows:end -->\r?$/ { skip = 0 }
')
section=$(<"${HERE}/release-notes.md.tmpl")
section=${section//@VERSION@/${VERSION}}
section=${section//@PS1_SHA256@/${PS1_SHA256}}
section=${section//@ROOTFS_SHA256@/${ROOTFS_SHA256}}

if [[ -n ${body} ]]; then
	printf '%s\n\n%s\n' "${body}" "${section}"
else
	printf '%s\n' "${section}"
fi
