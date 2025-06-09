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
    curl \
    nodejs \
    npm \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install pyenv
RUN curl -fsSL https://pyenv.run | bash
ENV PYENV_ROOT="/root/.pyenv"
ENV PATH="${PYENV_ROOT}/bin:${PYENV_ROOT}/shims:${PATH}"

# Create a non-root user
RUN groupadd -r romm && useradd -r -g romm -m -s /bin/bash romm

# Set working directory
WORKDIR /app

# Install Python 3.12
# ENV PYENV_ROOT="/root/.pyenv"
# ENV PATH="${PYENV_ROOT}/bin:${PYENV_ROOT}/shims:${PATH}"
RUN pyenv install 3.12 && pyenv global 3.12

# Install pipx and poetry for the non-root user
RUN pip3 install pipx poetry \
    && pip3 install --user pipx \
    && python3 -m pipx ensurepath

# Make poetry available to all users
ENV PATH="/usr/local/bin:${PATH}"

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

# Install Python dependencies
RUN poetry sync

# Set environment variable to fix keyring issues
# ENV PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh && \
    # Make sure the non-root user can access necessary directories
    chown -R romm:romm /app /entrypoint.sh

# Switch to non-root user
USER romm

# Add health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/entrypoint.sh"]
