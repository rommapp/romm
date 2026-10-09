# checkov:skip=CKV_DOCKER_2:a WSL rootfs, not a container; RomM.ps1 polls /api/heartbeat
# checkov:skip=CKV_DOCKER_3:WSL runs the launcher as root so it can bind-mount the library
# checkov:skip=CKV_DOCKER_7:the base tag comes from the ROMM_IMAGE arg, pinned to a release
# Turns the RomM image into a WSL2 distro rootfs: adds a local MariaDB and a
# launcher, since WSL has no compose to run the database next to RomM.
ARG ROMM_IMAGE=rommapp/romm:5.3.1
FROM ${ROMM_IMAGE}

SHELL ["/bin/bash", "-o", "pipefail", "-c"]

# Unpinned like the main image's apk packages: Alpine drops old versions from its repo.
# hadolint ignore=DL3018
RUN apk add --no-cache mariadb mariadb-client

COPY ./rootfs/wsl.conf /etc/wsl.conf
COPY --chmod=755 ./rootfs/romm-wsl.sh /usr/local/bin/romm-wsl

# WSL mounts its own init binary over /init, so RomM's init needs another path.
# `docker export` drops ENV, so keep the image's environment for the launcher.
RUN cp /init /usr/local/bin/romm-init && \
    mkdir -p /etc/romm && \
    bash -c 'export -p' | grep -vE ' (HOME|HOSTNAME|OLDPWD|PWD|SHLVL|_)(=|$)' >/etc/romm/image.env
