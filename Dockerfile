# trunk-ignore-all(trivy)
# trunk-ignore-all(checkov)

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
