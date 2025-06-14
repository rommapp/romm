# trunk-ignore-all(trivy)
# trunk-ignore-all(checkov)

FROM ubuntu:22.04

# Prevent interactive prompts during installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    make \
    gcc \
    g++ \
    libmariadb3 \
    libmariadb-dev \
    libpq-dev \
    libffi-dev \
    libpq-dev \
    musl-dev \
    curl \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install pyenv
RUN curl -fsSL https://pyenv.run | bash
ENV PYENV_ROOT="/root/.pyenv"
ENV PATH="${PYENV_ROOT}/bin:${PYENV_ROOT}/shims:${PATH}"

# Install nvm
ENV NVM_DIR="/root/.nvm"
RUN curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash \
    && . "$NVM_DIR/nvm.sh" \
    && nvm install 18.20.8 \
    && nvm use 18.20.8 \
    && nvm alias default 18.20.8
ENV PATH="$NVM_DIR/versions/node/v18.20.8/bin:$PATH"

# Set working directory
WORKDIR /app

# Install Python 3.12
RUN pyenv install 3.12 && pyenv global 3.12

# Install pipx and poetry for the non-root user
RUN pip3 install pipx poetry \
    && pip3 install --user pipx \
    && python3 -m pipx ensurepath

# Make poetry available to all users
ENV PATH="/usr/local/bin:$HOME/.local/bin:${PATH}"

# Install Trunk CLI
RUN curl https://get.trunk.io -fsSL | bash

# Build and install RAHasher (optional for RA hashes)
RUN git clone --recursive --branch 1.8.0 --depth 1 https://github.com/RetroAchievements/RALibretro.git /tmp/RALibretro
WORKDIR /tmp/RALibretro
RUN sed -i '22a #include <ctime>' ./src/Util.h \
    && make HAVE_CHD=1 -f ./Makefile.RAHasher \
    && cp ./bin64/RAHasher /usr/bin/RAHasher
WORKDIR /app

RUN rm -rf /tmp/RALibretro

# Copy project files (including pyproject.toml and poetry.lock)
COPY pyproject.toml poetry.lock* .env .python-version ./

# Install Python dependencies
RUN poetry sync

# Copy frontend files
COPY frontend/package*.json ./frontend/

# Install frontend dependencies
RUN cd frontend && npm ci

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
