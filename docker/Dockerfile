# Build frontend
FROM node:lts-alpine as front-build-stage
WORKDIR /front
COPY ./frontend ./
RUN npm install
RUN npm run build

# Setup frontend
FROM nginx:1.24-alpine3.17-slim as production-stage
ARG WEBSERVER_FOLDER=/var/www/html
COPY --from=front-build-stage /front/dist ${WEBSERVER_FOLDER}
COPY ./frontend/assets/default_avatar.png ${WEBSERVER_FOLDER}/assets/
COPY ./frontend/assets/platforms ${WEBSERVER_FOLDER}/assets/platforms
RUN mkdir -p ${WEBSERVER_FOLDER}/assets/romm && \
    ln -s /romm/library ${WEBSERVER_FOLDER}/assets/romm/library && \
    ln -s /romm/resources ${WEBSERVER_FOLDER}/assets/romm/resources

# Setup backend
RUN apk update && \
    apk add \
        bash \
        curl \
        gcc \
        musl-dev \
        netcat-openbsd \
        mariadb-connector-c \
        mariadb-connector-c-dev \
        python3 \
        python3-dev \
        py3-pip

WORKDIR /back
COPY ./pyproject.toml ./poetry.lock ./
RUN pip install --no-cache --upgrade pip && \
    pip install --no-cache poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-interaction --no-ansi --only main
COPY ./backend .

# Setup init script and config files
COPY ./docker/init_scripts/* /
COPY ./docker/nginx/default.conf /etc/nginx/nginx.conf

# cleanup build deps
RUN apk del \
        gcc \
        musl-dev \
        mariadb-connector-c-dev \
        python3-dev \
        py3-pip

FROM scratch
COPY --from=production-stage / /

# Expose ports and start
EXPOSE 8080
WORKDIR /romm
CMD ["/init"]
