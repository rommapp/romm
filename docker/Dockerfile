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

# Versions:
ARG ALPINE_VERSION=3.20
ARG NGINX_VERSION=1.27.1
ARG NODE_VERSION=20.16
ARG PYTHON_VERSION=3.12


FROM node:${NODE_VERSION}-alpine${ALPINE_VERSION} AS frontend-build
WORKDIR /front

COPY ./frontend/package*.json ./
RUN npm ci

COPY ./frontend ./
RUN npm run build


FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS backend-build

# git is needed to install py7zr fork
# libffi-dev is needed to fix poetry dependencies for >= v1.8 on arm64
# libpq-dev is needed to build psycopg-c
# mariadb-connector-c-dev is needed to build mariadb-connector
RUN apk add --no-cache \
    gcc \
    git \
    libffi-dev \
    libpq-dev \
    mariadb-connector-c-dev \
    musl-dev

RUN pip install poetry

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

WORKDIR /src

COPY ./pyproject.toml ./poetry.lock /src/
RUN poetry install --no-ansi --no-cache --only main


FROM backend-build AS backend-dev-build

RUN poetry install --no-ansi --no-cache


# TODO: Upgrade Alpine to the same version as the other stages, when RAHasher is updated to work
#       with it (seems like Alpine 3.18's g++ v12 is the latest version that works with RAHasher,
#       while g++ v13 fails to compile it).
FROM alpine:3.18 AS rahasher-build

RUN apk add --no-cache \
    g++ \
    git \
    linux-headers \
    make \
    zlib-dev

ARG RALIBRETRO_VERSION=1.8.0

# TODO: Remove `sed` command when RAHasher can be compiled without it.
RUN git clone --recursive --branch "${RALIBRETRO_VERSION}" --depth 1 https://github.com/RetroAchievements/RALibretro.git && \
    cd ./RALibretro && \
    sed -i '22a #include <ctime>' ./src/Util.h && \
    make HAVE_CHD=1 -f ./Makefile.RAHasher


FROM alpine:${ALPINE_VERSION} AS emulator-stage

RUN apk add --no-cache \
    7zip \
    wget

ARG EMULATORJS_VERSION=4.2.0
RUN wget "https://github.com/EmulatorJS/EmulatorJS/releases/download/v${EMULATORJS_VERSION}/${EMULATORJS_VERSION}.7z" && \
    7z x -y "${EMULATORJS_VERSION}.7z" -o/emulatorjs && \
    rm -rf "${EMULATORJS_VERSION}.7z";

ARG RUFFLE_VERSION=nightly-2024-12-28
ARG RUFFLE_FILE=ruffle-nightly-2024_12_28-web-selfhosted.zip
RUN wget "https://github.com/ruffle-rs/ruffle/releases/download/${RUFFLE_VERSION}/${RUFFLE_FILE}" && \
    unzip -o "${RUFFLE_FILE}" -d /ruffle && \
    rm -f "${RUFFLE_FILE}";

FROM alpine:${ALPINE_VERSION} AS nginx-build

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
ARG NGINX_MOD_ZIP_SHA=8e65b82c82c7890f67a6107271c127e9881b6313

# Clone both nginx and `ngx_http_zip_module` repositories, needed to compile the module from source.
# This is needed to be able to dinamically load it as a module in the final image. `nginx` Docker
# images do not have a simple way to include third-party modules.
RUN git clone https://github.com/evanmiller/mod_zip.git && \
    cd ./mod_zip && \
    git checkout "${NGINX_MOD_ZIP_SHA}" && \
    cd ../ && \
    git clone --branch "release-${NGINX_VERSION}" --depth 1 https://github.com/nginx/nginx.git && \
    cd ./nginx && \
    ./auto/configure --with-compat --add-dynamic-module=../mod_zip/ && \
    make -f ./objs/Makefile modules && \
    chmod 644 ./objs/ngx_http_zip_module.so


FROM nginx:${NGINX_VERSION}-alpine${ALPINE_VERSION} AS production-stage
ARG WEBSERVER_FOLDER=/var/www/html

# Install required packages and dependencies
RUN apk add --no-cache \
    bash \
    libmagic \
    mariadb-connector-c \
    libpq \
    p7zip \
    python3 \
    tzdata \
    valkey

COPY --from=rahasher-build /RALibretro/bin64/RAHasher /usr/bin/RAHasher
COPY --from=nginx-build ./nginx/objs/ngx_http_zip_module.so /usr/lib/nginx/modules/
COPY --from=frontend-build /front/dist ${WEBSERVER_FOLDER}

COPY ./frontend/assets/dashboard-icons ${WEBSERVER_FOLDER}/assets/dashboard-icons
COPY ./frontend/assets/default ${WEBSERVER_FOLDER}/assets/default
COPY ./frontend/assets/platforms ${WEBSERVER_FOLDER}/assets/platforms
COPY ./frontend/assets/scrappers ${WEBSERVER_FOLDER}/assets/scrappers
COPY ./frontend/assets/webrcade/feed ${WEBSERVER_FOLDER}/assets/webrcade/feed
COPY ./frontend/assets/emulatorjs ${WEBSERVER_FOLDER}/assets/emulatorjs
COPY ./frontend/assets/ruffle ${WEBSERVER_FOLDER}/assets/ruffle
RUN mkdir -p ${WEBSERVER_FOLDER}/assets/romm && \
    ln -s /romm/resources ${WEBSERVER_FOLDER}/assets/romm/resources && \
    ln -s /romm/assets ${WEBSERVER_FOLDER}/assets/romm/assets

COPY ./backend /backend

# Setup init script and config files
COPY ./docker/init_scripts/* /
COPY ./docker/nginx/js/ /etc/nginx/js/
COPY ./docker/nginx/default.conf /etc/nginx/nginx.conf

# User permissions
RUN addgroup -g 1000 -S romm && adduser -u 1000 -D -S -G romm romm && \
    mkdir /romm /redis-data && chown romm:romm /romm /redis-data


FROM scratch AS slim-image

COPY --from=production-stage / /

COPY --from=backend-build /src/.venv /src/.venv
# Fix virtualenv link to python binary
RUN ln -sf "$(which python)" /src/.venv/bin/python

ENV PATH="/src/.venv/bin:${PATH}"

# Declare the supported volumes
VOLUME ["/romm/resources", "/romm/library", "/romm/assets", "/romm/config", "/redis-data"]

# Expose ports and start
EXPOSE 8080 6379/tcp
WORKDIR /romm

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["/init"]


FROM slim-image AS full-image
ARG WEBSERVER_FOLDER=/var/www/html
COPY --from=emulator-stage /emulatorjs ${WEBSERVER_FOLDER}/assets/emulatorjs
COPY --from=emulator-stage /ruffle ${WEBSERVER_FOLDER}/assets/ruffle


FROM slim-image AS dev-slim
COPY --from=backend-dev-build /src/.venv /src/.venv
# Fix virtualenv link to python binary
RUN ln -sf "$(which python)" /src/.venv/bin/python


FROM full-image AS dev-full
COPY --from=backend-dev-build /src/.venv /src/.venv
# Fix virtualenv link to python binary
RUN ln -sf "$(which python)" /src/.venv/bin/python
