# syntax=docker/dockerfile:1
# trunk-ignore-all(trivy)
# trunk-ignore-all(checkov)
# trunk-ignore-all(hadolint/DL4006)
# The stages mirror docker/Dockerfile, which pins Alpine rather than each apk package.
# trunk-ignore-all(hadolint/DL3003,hadolint/DL3013,hadolint/DL3018)

# Same bases as docker/Dockerfile, so system tools (7zip, libmagic, libarchive)
# match production. Keep these pins in sync with its ARGUMENT DECLARATIONS.
ARG ALPINE_VERSION=3.24
ARG ALPINE_SHA256=294b683cb724975bec92580e1e685676bd4b50bda910ddb8c51d4cabeaec77e6
# Pins the base image tag, so it cannot read .python-version; keep the two in sync.
ARG PYTHON_VERSION=3.14
ARG PYTHON_ALPINE_SHA256=9e9fde4d32eedce0b661d9ab91e826b62dddf28e928c230ec55f1866cac66b01
ARG NODE_VERSION=24.22
ARG NODE_ALPINE_SHA256=6a1c190e17215d844926b0677f4bf87273ff7d5e54db06d3b5b5863ab0b09a3d
ARG UV_VERSION=0.13.4
ARG UV_SHA256=0cb69bb18ffcd57db04f045010b0234132a111da70dde5a393d26ad288d38e13
ARG EMSDK_VERSION=4.0.12
ARG EMSDK_AMD64_SHA256=744fb6a68941970951bacf9d6632041a0398260492232691ef22bbf54b0585c6
ARG EMSDK_ARM64_SHA256=369a4cb655aa1066e6e450dde774243c502d999b1d93fb4890a9d1428daa9280
ARG GME_VERSION=0.6.5
ARG GME_COMMIT=9e23d10f9fd2a6a2f33b10912dd8dc7153258995


# trunk-ignore(hadolint/DL3029)
FROM --platform=linux/amd64 emscripten/emsdk:${EMSDK_VERSION}@sha256:${EMSDK_AMD64_SHA256} AS emsdk-amd64
# trunk-ignore(hadolint/DL3029)
FROM --platform=linux/arm64 emscripten/emsdk:${EMSDK_VERSION}-arm64@sha256:${EMSDK_ARM64_SHA256} AS emsdk-arm64
# trunk-ignore(hadolint/DL3006)
FROM emsdk-${BUILDARCH} AS gme-build
ARG GME_VERSION
ARG GME_COMMIT
ADD --checksum=${GME_COMMIT} "https://github.com/libgme/game-music-emu.git#${GME_VERSION}" /libgme
COPY docker/gme /romm-gme
RUN /romm-gme/build.sh /libgme /gme


FROM node:${NODE_VERSION}-alpine${ALPINE_VERSION}@sha256:${NODE_ALPINE_SHA256} AS node-stage


# https://github.com/astral-sh/uv/pkgs/container/uv
FROM ghcr.io/astral-sh/uv:${UV_VERSION}-python${PYTHON_VERSION}-alpine@sha256:${UV_SHA256} AS uv-stage


# Tag 1.8.3. Keep the pin and the musl patches in sync with docker/Dockerfile.
FROM alpine:${ALPINE_VERSION}@sha256:${ALPINE_SHA256} AS rahasher-build
RUN apk add --no-cache \
    g++ \
    git \
    linux-headers \
    make \
    zlib-dev \
    bash

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


# Built on the Python image so the cffi extension matches the venv's CPython ABI.
# Keep the pin in sync with docker/Dockerfile.
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION}@sha256:${PYTHON_ALPINE_SHA256} AS sigil-build
RUN apk add --no-cache \
    cmake \
    g++ \
    git \
    make \
    musl-dev

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


# Keep the version and both sums in sync with docker/Dockerfile.
FROM alpine:${ALPINE_VERSION}@sha256:${ALPINE_SHA256} AS rom-converto-fetch
ARG TARGETARCH
ARG ROM_CONVERTO_VERSION=v0.24.0
RUN case "${TARGETARCH}" in \
        amd64) rc="linux-x64-musl"; sum="67964054931f7e74848bfe7b54ff1f0cacdc25596c29e3a79876f76e0f2407a8" ;; \
        arm64) rc="linux-arm64-musl"; sum="60f9dc0fe7c3e3355c840c5e21c2b65b770b74ba78567aec7a2e5f846b8087ce" ;; \
        *) echo "unsupported TARGETARCH: ${TARGETARCH}" && exit 1 ;; \
    esac && \
    wget -qO /rom-converto \
        "https://github.com/DevYukine/rom-converto/releases/download/${ROM_CONVERTO_VERSION}/rom-converto-cli-${rc}" && \
    echo "${sum}  /rom-converto" | sha256sum -c - && \
    chmod 0755 /rom-converto


# Browser player runtimes. Keep the pins in sync with the emulator stage of docker/Dockerfile.
FROM alpine:${ALPINE_VERSION}@sha256:${ALPINE_SHA256} AS emulator-download

RUN apk add --no-cache \
    7zip

ARG EMULATORJS_VERSION=4.2.3
ARG EMULATORJS_SHA256=07d451bc06fa3ad04ab30d9b94eb63ac34ad0babee52d60357b002bde8f3850b

ADD --checksum=sha256:${EMULATORJS_SHA256} \
    "https://github.com/EmulatorJS/EmulatorJS/releases/download/v${EMULATORJS_VERSION}/${EMULATORJS_VERSION}.7z" \
    /downloads/emulatorjs.7z
RUN 7zz x -y /downloads/emulatorjs.7z -o/emulators/emulatorjs

ARG RUFFLE_VERSION=nightly-2025-08-14
ARG RUFFLE_FILE=ruffle-nightly-2025_08_14-web-selfhosted.zip
ARG RUFFLE_SHA256=178870c5e7dd825a8df35920dfc5328d83e53f3c4d5d95f70b1ea9cd13494151

ADD --checksum=sha256:${RUFFLE_SHA256} \
    "https://github.com/ruffle-rs/ruffle/releases/download/${RUFFLE_VERSION}/${RUFFLE_FILE}" \
    /downloads/ruffle.zip
RUN 7zz x -y /downloads/ruffle.zip -o/emulators/ruffle

ARG JSDOS_VERSION=8.4.1
ARG JSDOS_SHA256=26118692bbb180aec78ec1697eb1ea6b28ff410101870cfa3e68309914c7eaa6

ADD --checksum=sha256:${JSDOS_SHA256} \
    "https://github.com/caiiiycuk/js-dos/releases/download/v${JSDOS_VERSION}/release.zip" \
    /downloads/jsdos.zip
# The bundled index.html is a js-dos demo page that would be served unauthenticated;
# source maps, Emscripten symbol files and type declarations are unused at runtime.
RUN 7zz x -y /downloads/jsdos.zip -o/tmp/jsdos \
    && mv /tmp/jsdos/dist /emulators/jsdos \
    && rm -rf /emulators/jsdos/index.html /emulators/jsdos/emulators/types \
    && find /emulators/jsdos \( -name '*.map' -o -name '*.symbols' \) -exec rm -f {} +

# FAKE-08 (MIT) publishes no web build, so these come from p3a (Apache-2.0),
# which compiled them. Pinned by commit and checksum: that tree has no tags.
ARG FAKE08_P3A_COMMIT=6519efd9dd1ca853e5c66f7ae9146ace0b7073dc
ARG FAKE08_JS_SHA256=fd2cd4677956037e41a91dbd40fc1a9c4f5979355d55ce3f9312400e11da463e
ARG FAKE08_WASM_SHA256=4339a77e0aa5aa6f4a5bce9fd8286053eedf7f23f2d853db7f4900f6fff4c93a

# Created first, or ADD --chmod would also apply to the directory it creates.
RUN mkdir -p /emulators/pico8
ADD --checksum=sha256:${FAKE08_JS_SHA256} --chmod=644 \
    "https://raw.githubusercontent.com/fabkury/p3a/${FAKE08_P3A_COMMIT}/webui/pico8/fake08.js" \
    /emulators/pico8/fake08.js
ADD --checksum=sha256:${FAKE08_WASM_SHA256} --chmod=644 \
    "https://raw.githubusercontent.com/fabkury/p3a/${FAKE08_P3A_COMMIT}/webui/pico8/fake08.wasm" \
    /emulators/pico8/fake08.wasm

ARG EASYRPG_VERSION=0.8.1.1
ARG EASYRPG_SHA256=99b6963c943bb355e1b1221125cb4536ca2f627c329d8a89cee5a928cdd6a14f

ADD --checksum=sha256:${EASYRPG_SHA256} \
    "https://easyrpg.org/downloads/player/${EASYRPG_VERSION}/easyrpg-player-${EASYRPG_VERSION}-js.tar.gz" \
    /downloads/easyrpg.tar.gz
# games/ is where the player looks for games, which the server routes to the backend.
RUN mkdir -p /emulators/easyrpg && \
    tar -xzf /downloads/easyrpg.tar.gz -C /emulators/easyrpg --strip-components=1 && \
    rm -rf /emulators/easyrpg/games

# The free RTP (CC-BY-4.0) has no releases, so it is pinned by commit.
ARG EASYRPG_RTP_COMMIT=993d88cbc78c658d348bbfa74a3b424d393d27e5
ARG EASYRPG_RTP_SHA256=7e42abebbec94989f4ff214fc082511eef749114e76e3a342cb62d07c03d56e7

ADD --checksum=sha256:${EASYRPG_RTP_SHA256} \
    "https://github.com/EasyRPG/RTP/archive/${EASYRPG_RTP_COMMIT}.tar.gz" \
    /downloads/easyrpg-rtp.tar.gz
RUN mkdir /emulators/easyrpg/rtp && \
    tar -xzf /downloads/easyrpg-rtp.tar.gz -C /emulators/easyrpg/rtp --strip-components=1 && \
    find /emulators/easyrpg/rtp \( -name '.git*' -o -name Makefile \) -exec rm -f {} +


FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION}@sha256:${PYTHON_ALPINE_SHA256}

# Runtime packages match production-stage in docker/Dockerfile; the rest build
# Python dependencies from source (memray has no arm64 musl wheel).
RUN apk upgrade --no-cache && apk add --no-cache \
    bash \
    libarchive-tools \
    libmagic \
    mariadb-connector-c \
    libpq \
    7zip \
    tzdata \
    curl \
    cmake \
    elfutils-dev \
    g++ \
    gcc \
    git \
    libpq-dev \
    libstdc++ \
    libunwind-dev \
    linux-headers \
    lz4-dev \
    make \
    mariadb-connector-c-dev \
    musl-dev

COPY --from=node-stage /usr/local/bin/node /usr/local/bin/
COPY --from=node-stage /usr/local/lib/node_modules/npm /usr/local/lib/node_modules/npm
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
    && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

COPY --from=rahasher-build /RALibretro/bin64/RAHasher /usr/bin/RAHasher
COPY --from=rom-converto-fetch /rom-converto /usr/bin/rom-converto

# Install frontend dependencies
COPY frontend/package*.json /app/frontend/
WORKDIR /app/frontend
RUN npm ci --no-audit --no-fund

# Install backend Node helpers (server-side ROM patching)
COPY backend/utils/rom_patcher/package*.json /app/backend/utils/rom_patcher/
WORKDIR /app/backend/utils/rom_patcher
RUN npm ci --no-audit --no-fund

WORKDIR /app

COPY --from=uv-stage /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/

# Use the image's Python, as production does, rather than a uv-managed one.
ENV UV_PYTHON_DOWNLOADS=never

COPY pyproject.toml uv.lock* .python-version /app/
RUN uv sync --all-extras

ENV PATH="/app/.venv/bin:${PATH}"

# Optional sigil bindings for title ID extraction
ARG PYTHON_VERSION
COPY --from=sigil-build /sigil-pkg /app/.venv/lib/python${PYTHON_VERSION}/site-packages/sigil

# Kept outside /app/frontend because the ./frontend bind mount hides it;
# entrypoint.sh links the runtimes into the assets tree at startup.
ENV EMULATOR_ASSETS_DIR="/opt/romm/emulators"
COPY --from=emulator-download /emulators "${EMULATOR_ASSETS_DIR}"
COPY --from=gme-build /gme "${EMULATOR_ASSETS_DIR}/gme"

COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
