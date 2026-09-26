# trunk-ignore-all(trivy)
# trunk-ignore-all(checkov)
# trunk-ignore-all(hadolint/DL4006)

# Keep the pins in sync with the gme-build stage of docker/Dockerfile.
FROM emscripten/emsdk:4.0.12@sha256:744fb6a68941970951bacf9d6632041a0398260492232691ef22bbf54b0585c6 AS emsdk-amd64
FROM emscripten/emsdk:4.0.12-arm64@sha256:369a4cb655aa1066e6e450dde774243c502d999b1d93fb4890a9d1428daa9280 AS emsdk-arm64
# trunk-ignore(hadolint/DL3006)
FROM emsdk-${BUILDARCH} AS gme-build
ARG GME_VERSION=0.6.5
ARG GME_COMMIT=9e23d10f9fd2a6a2f33b10912dd8dc7153258995
COPY docker/gme /romm-gme
RUN git clone --depth 1 --branch "${GME_VERSION}" https://github.com/libgme/game-music-emu.git /libgme \
    && test "$(git -C /libgme rev-parse HEAD)" = "${GME_COMMIT}" \
    && /romm-gme/build.sh /libgme /gme

# Browser player runtimes. Keep the pins in sync with the emulator stage of docker/Dockerfile.
FROM ubuntu:22.04 AS emulator-download

# trunk-ignore(hadolint/DL3008)
RUN apt-get update && apt-get install -y --no-install-recommends \
    7zip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

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


FROM ubuntu:22.04

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    make \
    cmake \
    gcc \
    g++ \
    libmariadb3 \
    libmariadb-dev \
    libpq-dev \
    libffi-dev \
    musl-dev \
    curl \
    ca-certificates \
    libmagic-dev \
    7zip \
    libarchive-tools \
    tzdata \
    libbz2-dev \
    libssl-dev \
    libreadline-dev \
    libsqlite3-dev \
    zlib1g-dev \
    liblzma-dev \
    libncurses5-dev \
    libncursesw5-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install nvm
ENV NVM_DIR="/root/.nvm"
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash \
    && . "$NVM_DIR/nvm.sh" \
    && nvm install 24.16.0 \
    && nvm use 24.16.0 \
    && nvm alias default 24.16.0
ENV PATH="$NVM_DIR/versions/node/v24.16.0/bin:$PATH"

# Build and install RAHasher (optional for RA hashes)
# Tag 1.8.3. Keep the pin in sync with docker/Dockerfile.
ARG RALIBRETRO_COMMIT=8ab61f745ab753a70b5482f2a0ccb6a4ced5193f
RUN git clone --filter=blob:none https://github.com/RetroAchievements/RALibretro.git /tmp/RALibretro \
    && git -C /tmp/RALibretro checkout "${RALIBRETRO_COMMIT}" \
    && git -C /tmp/RALibretro submodule update --init --recursive
WORKDIR /tmp/RALibretro
RUN make HAVE_CHD=1 -f ./Makefile.RAHasher \
    && cp ./bin64/RAHasher /usr/bin/RAHasher
RUN rm -rf /tmp/RALibretro

# Install frontend dependencies
COPY frontend/package.json /app/frontend/
WORKDIR /app/frontend
RUN npm install

# Install backend Node helpers (server-side ROM patching)
COPY backend/utils/rom_patcher/package.json /app/backend/utils/rom_patcher/
WORKDIR /app/backend/utils/rom_patcher
RUN npm install

# Set working directory
WORKDIR /app

# Install uv for the non-root user
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /uvx /usr/local/bin/

# Copy project files (including pyproject.toml and uv.lock)
COPY pyproject.toml uv.lock* .python-version /app/

# Install Python (pinned by .python-version) and the project dependencies
RUN uv python install \
    && uv sync --all-extras

ENV PATH="/app/.venv/bin:${PATH}"

# Build and install sigil (optional, for title ID extraction)
# Placed after `uv sync` because the extension is compiled with the venv's
# Python so the ABI matches. Keep the pin in sync with docker/Dockerfile.
ARG SIGIL_VERSION=8a3b0089676e07f74da2d9ad08979dedf5cae7c0
# One layer, so the clone and the cmake tree never reach the image.
# trunk-ignore(hadolint/DL3003)
RUN git clone --filter=blob:none https://github.com/rommapp/argosy-sigil.git /tmp/argosy-sigil \
    && cd /tmp/argosy-sigil \
    && git checkout "${SIGIL_VERSION}" \
    && git submodule update --init --recursive \
    && cmake -B ./build-python -S . -DSIGIL_BUILD_CLI=OFF -DSIGIL_BUILD_TESTS=OFF \
    && cmake --build ./build-python --target sigil \
    && uv pip install --python /app/.venv/bin/python cffi setuptools \
    && cd ./bindings/python \
    && /app/.venv/bin/python build_sigil.py \
    && SITE_PACKAGES="$(/app/.venv/bin/python -c 'import site; print(site.getsitepackages()[0])')" \
    && mkdir -p "${SITE_PACKAGES}/sigil" \
    && cp ./sigil/*.py ./sigil/_sigil.*.so "${SITE_PACKAGES}/sigil/" \
    && rm -rf /tmp/argosy-sigil
WORKDIR /app

# Kept outside /app/frontend because the ./frontend bind mount hides it;
# entrypoint.sh links the runtimes into the assets tree at startup.
ENV EMULATOR_ASSETS_DIR="/opt/romm/emulators"
COPY --from=emulator-download /emulators "${EMULATOR_ASSETS_DIR}"
COPY --from=gme-build /gme "${EMULATOR_ASSETS_DIR}/gme"

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
