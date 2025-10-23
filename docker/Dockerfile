# Stages:
#   - frontend-build: Build frontend
#   - backend-build: Build backend environment
#   - backend-dev-build: Similar to `backend-build`, but also compiles and installs development dependencies
#   - rahasher-build: Build RAHasher
#   - emulator-stage: Fetch and extract emulators
#   - nginx-build: Build nginx modules
#   - production-stage: Setup frontend and backend
#   - slim-image: Slim image with only the necessary files
#   - full-image: Full image with emulator stage
#   - dev-slim: Slim image with development dependencies
#   - dev-full: Full image with emulator stage and development dependencies


# ARGUMENT DECLARATIONS
ARG ALPINE_VERSION=3.22
ARG ALPINE_SHA256=4b7ce07002c69e8f3d704a9c5d6fd3053be500b7f1c69fc0d80990c2ad8dd412
ARG PYTHON_VERSION=3.13
ARG PYTHON_ALPINE_SHA256=e5fa639e49b85986c4481e28faa2564b45aa8021413f31026c3856e5911618b1
ARG NODE_VERSION=20.19
ARG NODE_ALPINE_SHA256=96ee26670a085b1a61231a468db85ae7e493ddfbd8c35797bfa0b99b634665fe
ARG NGINX_VERSION=1.29.2
ARG NGINX_SHA256=61e01287e546aac28a3f56839c136b31f590273f3b41187a36f46f6a03bbfe22
ARG UV_VERSION=0.8.24
ARG UV_SHA256=779f3d612539b4696a1b228724cd79b6e8b8604075a9ac7d15378bccf4053373


FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION}@sha256:${PYTHON_ALPINE_SHA256} AS python-alias


# FRONTEND BUILD
FROM node:${NODE_VERSION}-alpine${ALPINE_VERSION}@sha256:${NODE_ALPINE_SHA256} AS frontend-build
WORKDIR /front

COPY ./frontend/package*.json ./
RUN npm ci --ignore-scripts --no-audit --no-fund

COPY ./frontend ./
RUN npm run build


# https://github.com/astral-sh/uv/pkgs/container/uv/452595714
FROM ghcr.io/astral-sh/uv:${UV_VERSION}-python${PYTHON_VERSION}-alpine@sha256:${UV_SHA256} AS uv-stage


# BACKEND PYTHON BUILD
FROM python-alias AS backend-build

# git is needed to install streaming-form-data fork
# libpq-dev is needed to build psycopg-c
# mariadb-connector-c-dev is needed to build mariadb-connector
RUN apk add --no-cache \
    gcc \
    git \
    libpq-dev \
    mariadb-connector-c-dev \
    musl-dev

COPY --from=uv-stage /usr/local/bin/uv /usr/local/bin/uvx /bin/

WORKDIR /src

COPY ./pyproject.toml ./uv.lock /src/
RUN uv sync --locked --no-cache

FROM backend-build AS backend-dev-build

# linux-headers is needed to install psutil
RUN apk add --no-cache \
    linux-headers

RUN uv sync --locked --no-cache --all-extras


# CUSTOM RAHASHER FOR RETROACHIEVEMENTS
FROM alpine:${ALPINE_VERSION}@sha256:${ALPINE_SHA256} AS rahasher-build
RUN apk add --no-cache \
    g++ \
    git \
    linux-headers \
    make \
    zlib-dev

ARG RALIBRETRO_VERSION=1.8.1

# TODO: Remove `sed` command adding "ctime", when RAHasher can be compiled without it.
# TODO: Remove `sed` command adding "unistd.h", when RAHasher can be compiled without it.
#       Related pull request: https://github.com/madler/zlib/pull/1022
RUN git clone --recursive --branch "${RALIBRETRO_VERSION}" --depth 1 https://github.com/RetroAchievements/RALibretro.git && \
    cd ./RALibretro && \
    sed -i '22a #include <ctime>' ./src/Util.h && \
    sed -i '6a #include <unistd.h>' \
      ./src/libchdr/deps/zlib-1.3.1/gzlib.c \
      ./src/libchdr/deps/zlib-1.3.1/gzread.c \
      ./src/libchdr/deps/zlib-1.3.1/gzwrite.c && \
    make HAVE_CHD=1 -f ./Makefile.RAHasher


# FETCH EMULATORJS AND RUFFLE
FROM alpine:${ALPINE_VERSION}@sha256:${ALPINE_SHA256} AS emulator-stage

RUN apk add --no-cache \
    7zip \
    wget \
    ca-certificates

ARG EMULATORJS_VERSION=4.2.3
ARG EMULATORJS_SHA256=07d451bc06fa3ad04ab30d9b94eb63ac34ad0babee52d60357b002bde8f3850b

RUN wget "https://github.com/EmulatorJS/EmulatorJS/releases/download/v${EMULATORJS_VERSION}/${EMULATORJS_VERSION}.7z" && \
    echo "${EMULATORJS_SHA256}  ${EMULATORJS_VERSION}.7z" | sha256sum -c - && \
    7z x -y "${EMULATORJS_VERSION}.7z" -o/emulatorjs && \
    rm -f "${EMULATORJS_VERSION}.7z"

ARG RUFFLE_VERSION=nightly-2025-08-14
ARG RUFFLE_FILE=ruffle-nightly-2025_08_14-web-selfhosted.zip
ARG RUFFLE_SHA256=178870c5e7dd825a8df35920dfc5328d83e53f3c4d5d95f70b1ea9cd13494151

RUN wget "https://github.com/ruffle-rs/ruffle/releases/download/${RUFFLE_VERSION}/${RUFFLE_FILE}" && \
    echo "${RUFFLE_SHA256}  ${RUFFLE_FILE}" | sha256sum -c - && \
    unzip -o "${RUFFLE_FILE}" -d /ruffle && \
    rm -f "${RUFFLE_FILE}"


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

RUN apk add --no-cache \
    bash \
    libmagic \
    mariadb-connector-c \
    libpq \
    7zip \
    tzdata \
    valkey

# Add Python by copying it from the official Docker image. This way, we don't rely on Alpine's
# Python version, which could not be the same as the one used in the backend build stage.
# TODO: Replace with a bundled installation of Python using `uv`, when it is supported.
#       Related issue: https://github.com/astral-sh/uv/issues/7865
ARG PYTHON_VERSION
COPY --from=python-alias /usr/lib/* /usr/lib/
COPY --from=python-alias /usr/local/bin/* /usr/local/bin/
COPY --from=python-alias /usr/local/include/python${PYTHON_VERSION} /usr/local/include/python${PYTHON_VERSION}
COPY --from=python-alias /usr/local/lib/libpython* /usr/local/lib/
COPY --from=python-alias /usr/local/lib/python${PYTHON_VERSION} /usr/local/lib/python${PYTHON_VERSION}

COPY --from=rahasher-build /RALibretro/bin64/RAHasher /usr/bin/RAHasher
COPY --from=nginx-build ./nginx/objs/ngx_http_zip_module.so /usr/lib/nginx/modules/
COPY --from=frontend-build /front/dist ${WEBSERVER_FOLDER}

COPY ./frontend/assets ${WEBSERVER_FOLDER}/assets
RUN mkdir -p ${WEBSERVER_FOLDER}/assets/romm && \
    ln -sf /romm/resources ${WEBSERVER_FOLDER}/assets/romm/resources && \
    ln -sf /romm/assets ${WEBSERVER_FOLDER}/assets/romm/assets
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
    chmod -R a+w /etc/nginx/conf.d


# SLIM IMAGE
FROM scratch AS slim-image

COPY --from=production-stage / /

COPY --from=backend-build /src/.venv /src/.venv

ENV PATH="/src/.venv/bin:${PATH}"

# Security: Set security-focused environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/backend

# Declare the supported volumes
VOLUME ["/romm/resources", "/romm/library", "/romm/assets", "/romm/config", "/redis-data"]

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


FROM slim-image AS dev-slim
COPY --from=backend-dev-build /src/.venv /src/.venv


FROM full-image AS dev-full
COPY --from=backend-dev-build /src/.venv /src/.venv
