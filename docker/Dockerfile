# Build frontend
FROM node:lts-alpine as front-build-stage
WORKDIR /front

COPY ./frontend/package*.json ./
RUN npm ci

COPY ./frontend ./
RUN npm run build

# Setup frontend and backend
FROM nginx:1.27.0-alpine3.19-slim as production-stage
ARG WEBSERVER_FOLDER=/var/www/html

COPY --from=front-build-stage /front/dist ${WEBSERVER_FOLDER}
COPY ./frontend/assets/default ${WEBSERVER_FOLDER}/assets/default
COPY ./frontend/assets/platforms ${WEBSERVER_FOLDER}/assets/platforms
COPY ./frontend/assets/webrcade/feed ${WEBSERVER_FOLDER}/assets/webrcade/feed
RUN mkdir -p ${WEBSERVER_FOLDER}/assets/romm && \
    ln -s /romm/resources ${WEBSERVER_FOLDER}/assets/romm/resources && \
    ln -s /romm/assets ${WEBSERVER_FOLDER}/assets/romm/assets

# Install required packages and dependencies
RUN apk add --no-cache \
        bash \
        curl \
        libffi \
        mariadb-connector-c \
        netcat-openbsd \
        python3 \
        tzdata \
        gcc \
        libffi-dev \
        mariadb-connector-c-dev \
        musl-dev \
        python3-dev \
        py3-pip \
        git \
        coreutils \
        make \
        openssl-dev \
        redis

# Create python venv and install dependencies
COPY ./pyproject.toml ./poetry.lock /
RUN python3 -m venv /backend/ && \
    . /backend/bin/activate && \
    pip install --no-cache --upgrade pip && \
    pip install --no-cache git+https://github.com/radoering/poetry.git@non-package-mode && \
    pip freeze | awk -F= '{print $1}' > /installed_pip_requirements.txt && \
    mkdir -p /root/.cache/pypoetry/virtualenvs && \
    python3 -m poetry config --no-cache virtualenvs.create false && \
    python3 -m poetry env use 3.11 && \
    python3 -m poetry install --no-interaction --no-ansi --no-cache --only main && \
    python3 -m poetry export --without-hashes --only main --without-urls | awk -F= '{print $1}' > /installed_poetry_requirements.txt && \
    grep -v -x -f /installed_poetry_requirements.txt /installed_pip_requirements.txt > /build_requirements.txt && \
    pip uninstall -y -r /build_requirements.txt

# Cleanup unnecessary packages and files
RUN apk del \
        gcc \
        libffi-dev \
        mariadb-connector-c-dev \
        musl-dev \
        python3-dev \
        py3-pip \
        git \
        coreutils \
        make \
        openssl-dev && \
    rm -r \
        /pyproject.toml \
        /poetry.lock \
        /installed_pip_requirements.txt \
        /installed_poetry_requirements.txt \
        /build_requirements.txt

COPY ./backend /backend

# Setup init script and config files
COPY ./docker/init_scripts/* /
COPY ./docker/nginx/default.conf /etc/nginx/nginx.conf

# User permissions
RUN addgroup -g 1000 -S romm && adduser -u 1000 -D -S -G romm romm && \
    mkdir /romm /redis-data && chown romm:romm /romm /redis-data

# Move everything to final stage
FROM scratch as final-stage
COPY --from=production-stage / /

# Declare the supported volumes
VOLUME ["/romm/resources", "/romm/library", "/romm/assets", "/romm/config", "/redis-data"]

# Expose ports and start
EXPOSE 8080
EXPOSE 6379/tcp
WORKDIR /romm
CMD ["/init"]
