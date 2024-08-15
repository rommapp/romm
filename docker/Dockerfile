ARG ALPINE_VERSION=3.20
ARG NGINX_VERSION=1.27.1
ARG NODE_VERSION=lts
ARG PYTHON_VERSION=3.12

# Build frontend
FROM node:${NODE_VERSION}-alpine${ALPINE_VERSION} AS front-build-stage
WORKDIR /front

COPY ./frontend/package*.json ./
RUN npm ci

COPY ./frontend ./
RUN npm run build

# Build backend environment
FROM python:${PYTHON_VERSION}-alpine${ALPINE_VERSION} AS backend-build

# libffi-dev is needed to fix poetry dependencies for >= v1.8 on arm64
RUN apk add --no-cache \
    gcc \
    mariadb-connector-c-dev \
    musl-dev \
    libffi-dev

RUN pip install poetry

ENV POETRY_NO_INTERACTION=1 \
    POETRY_VIRTUALENVS_IN_PROJECT=1

WORKDIR /src

COPY ./pyproject.toml ./poetry.lock /src/
RUN poetry install --no-ansi --no-cache --only main

# Setup frontend and backend
FROM nginx:${NGINX_VERSION}-alpine${ALPINE_VERSION}-slim AS production-stage
ARG WEBSERVER_FOLDER=/var/www/html

COPY --from=front-build-stage /front/dist ${WEBSERVER_FOLDER}
COPY ./frontend/assets/default ${WEBSERVER_FOLDER}/assets/default
COPY ./frontend/assets/emulatorjs ${WEBSERVER_FOLDER}/assets/emulatorjs
COPY ./frontend/assets/ruffle ${WEBSERVER_FOLDER}/assets/ruffle
COPY ./frontend/assets/scrappers ${WEBSERVER_FOLDER}/assets/scrappers
COPY ./frontend/assets/platforms ${WEBSERVER_FOLDER}/assets/platforms
COPY ./frontend/assets/webrcade/feed ${WEBSERVER_FOLDER}/assets/webrcade/feed
RUN mkdir -p ${WEBSERVER_FOLDER}/assets/romm && \
    ln -s /romm/resources ${WEBSERVER_FOLDER}/assets/romm/resources && \
    ln -s /romm/assets ${WEBSERVER_FOLDER}/assets/romm/assets

# Install required packages and dependencies
RUN apk add --no-cache \
    bash \
    mariadb-connector-c \
    python3 \
    tzdata \
    redis \
    libmagic \
    p7zip

COPY ./backend /backend

# Setup init script and config files
COPY ./docker/init_scripts/* /
COPY ./docker/nginx/default.conf /etc/nginx/nginx.conf

# User permissions
RUN addgroup -g 1000 -S romm && adduser -u 1000 -D -S -G romm romm && \
    mkdir /romm /redis-data && chown romm:romm /romm /redis-data

# Move everything to final stage
FROM scratch AS final-stage

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
CMD ["/init"]
