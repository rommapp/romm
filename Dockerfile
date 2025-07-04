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
    musl-dev \
    curl \
    ca-certificates \
    libmagic-dev \
    p7zip \
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
    && nvm install 18.20.8 \
    && nvm use 18.20.8 \
    && nvm alias default 18.20.8
ENV PATH="$NVM_DIR/versions/node/v18.20.8/bin:$PATH"

# Build and install RAHasher (optional for RA hashes)
RUN git clone --recursive --branch 1.8.1 --depth 1 https://github.com/RetroAchievements/RALibretro.git /tmp/RALibretro
WORKDIR /tmp/RALibretro
RUN sed -i '22a #include <ctime>' ./src/Util.h \
    && sed -i '6a #include <unistd.h>' \
      ./src/libchdr/deps/zlib-1.3.1/gzlib.c \
      ./src/libchdr/deps/zlib-1.3.1/gzread.c \
      ./src/libchdr/deps/zlib-1.3.1/gzwrite.c \
    && make HAVE_CHD=1 -f ./Makefile.RAHasher \
    && cp ./bin64/RAHasher /usr/bin/RAHasher
RUN rm -rf /tmp/RALibretro

# Install frontend dependencies
COPY frontend/package.json /app/frontend/
WORKDIR /app/frontend
RUN npm install

# Set working directory
WORKDIR /app

# Install uv for the non-root user
RUN curl -LsSf https://astral.sh/uv/install.sh | sh

# Make uv available to all users
ENV PATH="/usr/local/bin:$HOME/.local/bin:${PATH}"

# Copy project files (including pyproject.toml and uv.lock)
COPY pyproject.toml uv.lock* .python-version /app/

# Install Python and project dependencies
RUN uv install python 3.13
RUN uv sync --all-extras

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
