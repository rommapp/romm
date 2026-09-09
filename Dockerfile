# trunk-ignore-all(trivy)
# trunk-ignore-all(checkov)
# trunk-ignore-all(hadolint/DL4006): the checksum pipes read from echo, which cannot fail

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
RUN git clone --recursive --branch 1.8.3 --depth 1 https://github.com/RetroAchievements/RALibretro.git /tmp/RALibretro
WORKDIR /tmp/RALibretro
RUN make HAVE_CHD=1 -f ./Makefile.RAHasher \
    && cp ./bin64/RAHasher /usr/bin/RAHasher
RUN rm -rf /tmp/RALibretro

# Browser player runtimes, kept outside /app/frontend because the ./frontend
# bind mount hides it; entrypoint.sh links them into the assets tree at startup.
# Keep the pins in sync with the emulator stage of docker/Dockerfile.
ENV EMULATOR_ASSETS_DIR="/opt/romm/emulators"

ARG EMULATORJS_VERSION=4.2.3
ARG EMULATORJS_SHA256=07d451bc06fa3ad04ab30d9b94eb63ac34ad0babee52d60357b002bde8f3850b

RUN curl -fsSL -o /tmp/emulatorjs.7z "https://github.com/EmulatorJS/EmulatorJS/releases/download/v${EMULATORJS_VERSION}/${EMULATORJS_VERSION}.7z" \
    && echo "${EMULATORJS_SHA256}  /tmp/emulatorjs.7z" | sha256sum -c - \
    && 7zz x -y /tmp/emulatorjs.7z -o"${EMULATOR_ASSETS_DIR}/emulatorjs" \
    && rm -f /tmp/emulatorjs.7z

ARG RUFFLE_VERSION=nightly-2025-08-14
ARG RUFFLE_FILE=ruffle-nightly-2025_08_14-web-selfhosted.zip
ARG RUFFLE_SHA256=178870c5e7dd825a8df35920dfc5328d83e53f3c4d5d95f70b1ea9cd13494151

RUN curl -fsSL -o /tmp/ruffle.zip "https://github.com/ruffle-rs/ruffle/releases/download/${RUFFLE_VERSION}/${RUFFLE_FILE}" \
    && echo "${RUFFLE_SHA256}  /tmp/ruffle.zip" | sha256sum -c - \
    && 7zz x -y /tmp/ruffle.zip -o"${EMULATOR_ASSETS_DIR}/ruffle" \
    && rm -f /tmp/ruffle.zip

ARG JSDOS_VERSION=8.4.1
ARG JSDOS_SHA256=26118692bbb180aec78ec1697eb1ea6b28ff410101870cfa3e68309914c7eaa6

# The bundled index.html is a js-dos demo page that would be served unauthenticated;
# source maps, Emscripten symbol files and type declarations are unused at runtime.
RUN curl -fsSL -o /tmp/jsdos.zip "https://github.com/caiiiycuk/js-dos/releases/download/v${JSDOS_VERSION}/release.zip" \
    && echo "${JSDOS_SHA256}  /tmp/jsdos.zip" | sha256sum -c - \
    && 7zz x -y /tmp/jsdos.zip -o/tmp/jsdos \
    && mkdir -p "${EMULATOR_ASSETS_DIR}" \
    && mv /tmp/jsdos/dist "${EMULATOR_ASSETS_DIR}/jsdos" \
    && rm -rf /tmp/jsdos.zip /tmp/jsdos \
    && rm -rf "${EMULATOR_ASSETS_DIR}/jsdos/index.html" "${EMULATOR_ASSETS_DIR}/jsdos/emulators/types" \
    && find "${EMULATOR_ASSETS_DIR}/jsdos" \( -name '*.map' -o -name '*.symbols' \) -exec rm -f {} +

ARG FAKE08_P3A_COMMIT=6519efd9dd1ca853e5c66f7ae9146ace0b7073dc
ARG FAKE08_JS_SHA256=fd2cd4677956037e41a91dbd40fc1a9c4f5979355d55ce3f9312400e11da463e
ARG FAKE08_WASM_SHA256=4339a77e0aa5aa6f4a5bce9fd8286053eedf7f23f2d853db7f4900f6fff4c93a
ARG FAKE08_P3A_RAW=https://raw.githubusercontent.com/fabkury/p3a/${FAKE08_P3A_COMMIT}/webui/pico8

# FAKE-08 (MIT) publishes no web build, so these come from p3a (Apache-2.0),
# which compiled them. Pinned by commit and checksum: that tree has no tags.
RUN mkdir -p "${EMULATOR_ASSETS_DIR}/pico8" \
    && curl -fsSL -o "${EMULATOR_ASSETS_DIR}/pico8/fake08.js" "${FAKE08_P3A_RAW}/fake08.js" \
    && curl -fsSL -o "${EMULATOR_ASSETS_DIR}/pico8/fake08.wasm" "${FAKE08_P3A_RAW}/fake08.wasm" \
    && echo "${FAKE08_JS_SHA256}  ${EMULATOR_ASSETS_DIR}/pico8/fake08.js" | sha256sum -c - \
    && echo "${FAKE08_WASM_SHA256}  ${EMULATOR_ASSETS_DIR}/pico8/fake08.wasm" | sha256sum -c -

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
COPY --from=ghcr.io/astral-sh/uv:0.11.2 /uv /uvx /usr/local/bin/

# Copy project files (including pyproject.toml and uv.lock)
COPY pyproject.toml uv.lock* .python-version /app/

# Install Python (pinned by .python-version) and the project dependencies
RUN uv python install \
    && uv sync --all-extras

ENV PATH="/app/.venv/bin:${PATH}"

# Build and install sigil (optional, for title ID extraction)
# Placed after `uv sync` because the extension is compiled with the venv's
# Python so the ABI matches. Keep the pin in sync with docker/Dockerfile.
ARG SIGIL_VERSION=9665f03c04d0f547ed38dd5e5e31916c1da5f2e9
# One layer, so the clone and the cmake tree never reach the image.
# trunk-ignore(hadolint/DL3003)
RUN git clone --filter=blob:none https://github.com/rommforge/argosy-sigil.git /tmp/argosy-sigil \
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

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
