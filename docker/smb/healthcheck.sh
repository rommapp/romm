#!/bin/sh

set -eu

smbcontrol \
    --configfile=/run/samba/smb.conf \
    smbd ping 2>/dev/null | grep -q '^PONG from pid'
