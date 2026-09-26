# Stages:
#   - python-runtime: Patch the Python image's libraries before they ship
#   - frontend-build: Build frontend
#   - backend-build: Build backend environment
#   - backend-dev-build: Similar to `backend-build`, but also compiles and installs development dependencies
#   - rahasher-build: Build RAHasher
#   - sigil-build: Build sigil Python bindings (title ID extraction)
#   - gme-build: Build libgme to WebAssembly (chiptune soundtracks)
#   - emulator-stage: Fetch and extract emulators
#   - nginx-build: Build nginx modules
#   - production-stage: Setup frontend and backend
#   - slim-image: Slim image with only the necessary files
#   - full-image: Full image with emulator stage
#   - dev-slim: Slim image with development dependencies
#   - dev-full: Full image with emulator stage and development dependencies


# ARGUMENT DECLARATIONS
ARG ALPINE_VERSION=3.24
ARG ALPINE_SHA256=294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6
# Pins the base image tag, so it cannot read ../.python-version; keep the two in sync.
ARG PYTHON_VERSION=3.14
ARG PYTHON_ALPINE_SHA256=9e9fde4d32eedce0b661d9ab91e826b62dddf28e928c230ec55f1866cac66b01
ARG NODE_VERSION=24.16
ARG NODE_ALPINE_SHA256=21f403ab171f2dc89bad4dd69d7721bfd15f084ccb46cdd225f31f2bc59b5c9a
ARG NGINX_VERSION=1.30.5
ARG NGINX_SHA256=a5f2157a0302eb0c5e300415effb63a9e70ed1eb9c107283819bf6d149ab607c
ARG UV_VERSION=0.12.13
ARG UV_SHA256=eb47c391d3a252d9d912270dd2b5e234af5493e92039fedb483f1dd1cb5659ce
ARG EMSDK_VERSION=4.0.12
ARG EMSDK_AMD64_SHA256=744fb6a68941970951bacf9d6632041a0398260492232691ef22bbf54b0585c6
ARG EMSDK_ARM64_SHA256=369a4cb655aa1066e6e450dde774243c502d999b1d93fb4890a9d1428daa9280


FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION}@sha256:${PYTHON_ALPINE_SHA256} AS python-alias


# PATCHED PYTHON RUNTIME
# production-stage copies /usr/lib from here over its own, so these libraries
# need the same patches, or the stale ones land in the final image. Kept apart
# from python-alias so that busting this layer's cache (see `no-cache-filters`
# in build.yml) does not also rebuild the venv and the sigil bindings.
FROM python-alias AS python-runtime
RUN apk upgrade --no-cache


# FRONTEND BUILD
# Built on the native build platform: the output (/front/dist) is static JS/CSS,
# fully architecture-independent, so there is no need to emulate the target arch.
FROM --platform=$BUILDPLATFORM node:${NODE_VERSION}-alpine${ALPINE_VERSION}@sha256:${NODE_ALPINE_SHA256} AS frontend-build
WORKDIR /front

COPY ./frontend/package*.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

COPY ./frontend ./
RUN npm run build


# BACKEND NODE HELPERS BUILD (server-side ROM patching via RomPatcher.js)
FROM node:${NODE_VERSION}-alpine${ALPINE_VERSION}@sha256:${NODE_ALPINE_SHA256} AS backend-node-build
WORKDIR /backend-node/rom_patcher
COPY ./backend/utils/rom_patcher/package*.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund


# https://github.com/astral-sh/uv/pkgs/container/uv/452595714
FROM ghcr.io/astral-sh/uv:${UV_VERSION}-python${PYTHON_VERSION}-alpine@sha256:${UV_SHA256} AS uv-stage


# BACKEND PYTHON BUILD
FROM python-alias AS backend-build

# libpq-dev is needed to build psycopg-c
# mariadb-connector-c-dev is needed to build mariadb-connector
RUN apk add --no-cache \
    gcc \
    libpq-dev \
    mariadb-connector-c-dev \
    musl-dev

COPY --from=uv-stage /usr/local/bin/uv /usr/local/bin/uvx /bin/

WORKDIR /src

COPY ./pyproject.toml ./uv.lock /src/
RUN uv sync --frozen --no-cache

FROM backend-build AS backend-dev-build

# linux-headers is needed to install psutil
RUN apk add --no-cache \
    linux-headers

RUN uv sync --frozen --no-cache --all-extras


# CUSTOM RAHASHER FOR RETROACHIEVEMENTS
FROM alpine:${ALPINE_VERSION}@sha256:${ALPINE_SHA256} AS rahasher-build
RUN apk add --no-cache \
    g++ \
    git \
    linux-headers \
    make \
    zlib-dev \
    bash

# Tag 1.8.3. Pinned by commit because a tag can be moved.
# Keep this pin in sync with the dev image's RALIBRETRO_COMMIT in ../Dockerfile.
ARG RALIBRETRO_COMMIT=8ab61f745ab753a70b5482f2a0ccb6a4ced5193f

RUN git clone --filter=blob:none https://github.com/RetroAchievements/RALibretro.git && \
    cd ./RALibretro && \
    git checkout "${RALIBRETRO_COMMIT}" && \
    git submodule update --init --recursive && \
    sed -i '22a #include <ctime>' ./src/Util.h && \
    sed -i '6a #include <unistd.h>' \
        ./src/libchdr/deps/zlib-1.3.1/gzlib.c \
        ./src/libchdr/deps/zlib-1.3.1/gzread.c \
        ./src/libchdr/deps/zlib-1.3.1/gzwrite.c && \
    make HAVE_CHD=1 -f ./Makefile.RAHasher


# SIGIL TITLE ID EXTRACTION LIBRARY
# Built from python-alias (not plain alpine) so the cffi extension matches the
# CPython ABI of the venv produced in backend-build.
FROM python-alias AS sigil-build
RUN apk add --no-cache \
    cmake \
    g++ \
    git \
    make \
    musl-dev

# Keep this pin in sync with the dev image's SIGIL_VERSION in ../Dockerfile.
ARG SIGIL_VERSION=8a3b0089676e07f74da2d9ad08979dedf5cae7c0

RUN git clone --filter=blob:none https://github.com/rommapp/argosy-sigil.git && \
    cd ./argosy-sigil && \
    git checkout "${SIGIL_VERSION}" && \
    git submodule update --init --recursive && \
    cmake -B ./build-python -S . -DSIGIL_BUILD_CLI=OFF -DSIGIL_BUILD_TESTS=OFF && \
    cmake --build ./build-python --target sigil && \
    pip install --no-cache-dir cffi setuptools && \
    cd ./bindings/python && \
    python build_sigil.py && \
    mkdir /sigil-pkg && \
    cp ./sigil/*.py ./sigil/_sigil.*.so /sigil-pkg/


# LIBGME (LGPL-2.1+) FOR CHIPTUNE SOUNDTRACKS
# The WebAssembly output is the same on every platform, so it builds with the
# builder's own emsdk, which ships as a separate image per architecture.
# Keep the pins below in sync with the dev image's copies in ../Dockerfile.
FROM emscripten/emsdk:${EMSDK_VERSION}@sha256:${EMSDK_AMD64_SHA256} AS emsdk-amd64
FROM emscripten/emsdk:${EMSDK_VERSION}-arm64@sha256:${EMSDK_ARM64_SHA256} AS emsdk-arm64

# trunk-ignore(hadolint/DL3006,checkov/CKV_DOCKER_7)
FROM emsdk-${BUILDARCH} AS gme-build

ARG GME_VERSION=0.6.5
ARG GME_COMMIT=9e23d10f9fd2a6a2f33b10912dd8dc7153258995

COPY ./docker/gme /romm-gme
RUN git clone --depth 1 --branch "${GME_VERSION}" https://github.com/libgme/game-music-emu.git /libgme && \
    test "$(git -C /libgme rev-parse HEAD)" = "${GME_COMMIT}" && \
    /romm-gme/build.sh /libgme /gme


# FETCH EMULATORJS, RUFFLE, JS-DOS AND FAKE-08
# Keep the pins below in sync with the dev image's copies in ../Dockerfile.
# checkov:skip=CKV_DOCKER_4:every ADD below is a remote URL pinned by --checksum
FROM alpine:${ALPINE_VERSION}@sha256:${ALPINE_SHA256} AS emulator-stage

RUN apk add --no-cache \
    7zip

ARG EMULATORJS_VERSION=4.2.3
ARG EMULATORJS_SHA256=07d451bc06fa3ad04ab30d9b94eb63ac34ad0babee52d60357b002bde8f3850b

ADD --checksum=sha256:${EMULATORJS_SHA256} \
    "https://github.com/EmulatorJS/EmulatorJS/releases/download/v${EMULATORJS_VERSION}/${EMULATORJS_VERSION}.7z" \
    /downloads/emulatorjs.7z
RUN 7z x -y /downloads/emulatorjs.7z -o/emulatorjs

ARG RUFFLE_VERSION=nightly-2025-08-14
ARG RUFFLE_FILE=ruffle-nightly-2025_08_14-web-selfhosted.zip
ARG RUFFLE_SHA256=178870c5e7dd825a8df35920dfc5328d83e53f3c4d5d95f70b1ea9cd13494151

ADD --checksum=sha256:${RUFFLE_SHA256} \
    "https://github.com/ruffle-rs/ruffle/releases/download/${RUFFLE_VERSION}/${RUFFLE_FILE}" \
    /downloads/ruffle.zip
RUN unzip -o /downloads/ruffle.zip -d /ruffle

ARG JSDOS_VERSION=8.4.1
ARG JSDOS_SHA256=26118692bbb180aec78ec1697eb1ea6b28ff410101870cfa3e68309914c7eaa6

ADD --checksum=sha256:${JSDOS_SHA256} \
    "https://github.com/caiiiycuk/js-dos/releases/download/v${JSDOS_VERSION}/release.zip" \
    /downloads/jsdos.zip
# The bundled index.html is a js-dos demo page that would be served unauthenticated;
# source maps, Emscripten symbol files and type declarations are unused at runtime.
RUN unzip -o /downloads/jsdos.zip -d /jsdos && \
    rm -rf /jsdos/dist/index.html /jsdos/dist/emulators/types && \
    find /jsdos/dist \( -name '*.map' -o -name '*.symbols' \) -exec rm -f {} +

# FAKE-08 (MIT) publishes no web build, so these come from p3a (Apache-2.0),
# which compiled them. Pinned by commit and checksum: that tree has no tags.
ARG FAKE08_P3A_COMMIT=6519efd9dd1ca853e5c66f7ae9146ace0b7073dc
ARG FAKE08_JS_SHA256=fd2cd4677956037e41a91dbd40fc1a9c4f5979355d55ce3f9312400e11da463e
ARG FAKE08_WASM_SHA256=4339a77e0aa5aa6f4a5bce9fd8286053eedf7f23f2d853db7f4900f6fff4c93a

# Created first, or ADD --chmod would also apply to the directory it creates.
RUN mkdir /fake08
ADD --checksum=sha256:${FAKE08_JS_SHA256} --chmod=644 \
    "https://raw.githubusercontent.com/fabkury/p3a/${FAKE08_P3A_COMMIT}/webui/pico8/fake08.js" \
    /fake08/fake08.js
ADD --checksum=sha256:${FAKE08_WASM_SHA256} --chmod=644 \
    "https://raw.githubusercontent.com/fabkury/p3a/${FAKE08_P3A_COMMIT}/webui/pico8/fake08.wasm" \
    /fake08/fake08.wasm


# BUILD NGINX MODULE WITH MOD_ZIP
FROM alpine:${ALPINE_VERSION}@sha256:${ALPINE_SHA256} AS nginx-build

RUN apk add --no-cache \
    gcc \
    git \
    libc-dev \
    make \
    pcre-dev \
    zlib-dev

ARG NGINX_VERSION
# The specified commit SHA is the latest commit on the `master` branch at the time of writing.
# It includes a fix to correctly calculate CRC-32 checksums when using upstream subrequests.
# TODO: Move to a tagged release of `mod_zip`, once a version newer than 1.3.0 is released.
ARG NGINX_MOD_ZIP_COMMIT=a9f9afa441117831cc712a832c98408b3f0416f6

# Clone both `nginx` and `ngx_http_zip_module` repositories, needed to compile the module from source.
# This is needed to be able to dinamically load it as a module in the final image. `nginx` Docker
# images do not have a simple way to include third-party modules.
RUN git clone https://github.com/evanmiller/mod_zip.git && \
    cd ./mod_zip && \
    git checkout "${NGINX_MOD_ZIP_COMMIT}" && \
    cd ../ && \
    git clone --branch "release-${NGINX_VERSION}" --depth 1 https://github.com/nginx/nginx.git && \
    cd ./nginx && \
    ./auto/configure --with-compat --add-dynamic-module=../mod_zip/ && \
    make -f ./objs/Makefile modules && \
    chmod 644 ./objs/ngx_http_zip_module.so


# PRODUCTION STAGE
FROM nginx:${NGINX_VERSION}-alpine${ALPINE_VERSION}@sha256:${NGINX_SHA256} AS production-stage
ARG WEBSERVER_FOLDER=/var/www/html

# Alpine backports security fixes to its repo faster than the base image is
# rebuilt, so the digest pin alone leaves known-vulnerable packages in the image.
RUN apk upgrade --no-cache && apk add --no-cache \
    bash \
    libarchive-tools \
    libmagic \
    mariadb-connector-c \
    libpq \
    nodejs \
    7zip \
    tzdata \
    valkey \
    valkey-cli

# Add Python by copying it from the official Docker image. This way, we don't rely on Alpine's
# Python version, which could not be the same as the one used in the backend build stage.
# TODO: Replace with a bundled installation of Python using `uv`, when it is supported.
#       Related issue: https://github.com/astral-sh/uv/issues/7865
ARG PYTHON_VERSION
COPY --from=python-runtime /usr/lib/* /usr/lib/
COPY --from=python-runtime /usr/local/bin/* /usr/local/bin/
COPY --from=python-runtime /usr/local/include/python${PYTHON_VERSION} /usr/local/include/python${PYTHON_VERSION}
COPY --from=python-runtime /usr/local/lib/libpython* /usr/local/lib/
COPY --from=python-runtime /usr/local/lib/python${PYTHON_VERSION} /usr/local/lib/python${PYTHON_VERSION}

COPY --from=rahasher-build /RALibretro/bin64/RAHasher /usr/bin/RAHasher
COPY --from=nginx-build ./nginx/objs/ngx_http_zip_module.so /usr/lib/nginx/modules/
COPY --from=frontend-build /front/dist ${WEBSERVER_FOLDER}
COPY --from=backend-node-build /backend-node/rom_patcher/node_modules/rom-patcher/rom-patcher-js /backend/utils/rom_patcher/rom-patcher-js

COPY ./frontend/assets ${WEBSERVER_FOLDER}/assets
COPY --from=gme-build /gme ${WEBSERVER_FOLDER}/assets/gme
RUN mkdir -p ${WEBSERVER_FOLDER}/assets/romm && \
    ln -sf /romm/resources ${WEBSERVER_FOLDER}/assets/romm/resources
COPY ./backend /backend

# Setup init script and config files
COPY ./docker/init_scripts/* /
COPY ./docker/nginx/js/ /etc/nginx/js/
COPY ./docker/nginx/templates/ /etc/nginx/templates/
COPY ./docker/nginx/default.conf /etc/nginx/nginx.conf
COPY ./docker/gunicorn/logging.conf /etc/gunicorn/logging.conf

# User permissions
# - Create default user `romm` (1000) and group `romm` (1000).
# - Create base directories and make default user/group the owner.
# - Make nginx configuration files writable by everyone for `envsubst` to work
RUN addgroup -g 1000 -S romm && adduser -u 1000 -D -S -G romm romm && \
    mkdir /romm /redis-data && \
    chown romm:romm /romm /redis-data && \
    chmod 755 /romm /redis-data && \
    chmod -R a+w /etc/nginx/conf.d && \
    chmod -R a+w /etc/gunicorn


# SLIM IMAGE
FROM scratch AS slim-image

COPY --from=production-stage / /

COPY --from=backend-build /src/.venv /src/.venv

# Optional sigil bindings for title ID extraction; the backend feature
# no-ops when the package is absent.
ARG PYTHON_VERSION
COPY --from=sigil-build /sigil-pkg /src/.venv/lib/python${PYTHON_VERSION}/site-packages/sigil

ENV PATH="/src/.venv/bin:${PATH}"

# ScreenScraper developer (application) credentials, injected at build time from
# CI secrets. Kept out of the source tree; empty when not supplied at build.
ARG SCREENSCRAPER_DEV_ID
ARG SCREENSCRAPER_DEV_PASSWORD
ENV SCREENSCRAPER_DEV_ID=${SCREENSCRAPER_DEV_ID}
ENV SCREENSCRAPER_DEV_PASSWORD=${SCREENSCRAPER_DEV_PASSWORD}

# Security: Set security-focused environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/backend

# Declare only the parent `/romm`, not its subdirs, so Docker keeps them 
# on one mount (`st_dev`) and cross-directory `os.link()` hardlinks don't fail.
VOLUME ["/romm", "/redis-data"]

# Expose non-privileged ports
EXPOSE 8080 6379/tcp
WORKDIR /romm

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/init"]


# FULL IMAGE
FROM slim-image AS full-image
ARG WEBSERVER_FOLDER=/var/www/html
COPY --from=emulator-stage /emulatorjs ${WEBSERVER_FOLDER}/assets/emulatorjs
COPY --from=emulator-stage /ruffle ${WEBSERVER_FOLDER}/assets/ruffle
COPY --from=emulator-stage /jsdos/dist ${WEBSERVER_FOLDER}/assets/jsdos
COPY --from=emulator-stage /fake08 ${WEBSERVER_FOLDER}/assets/pico8


FROM slim-image AS dev-slim
COPY --from=backend-dev-build /src/.venv /src/.venv


FROM full-image AS dev-full
COPY --from=backend-dev-build /src/.venv /src/.venv
