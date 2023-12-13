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

# install generall required packages
RUN apk add --upgrade \
        bash \
        curl \
        libffi \
        mariadb-connector-c \
        netcat-openbsd \
        python3

# Install additional build dependencies
RUN apk add --upgrade \
        gcc \
        libffi-dev \
        mariadb-connector-c-dev \
        musl-dev \
        python3-dev \
        py3-pip

# Create python venv to not clash with OS python packages
RUN python3 -m venv /backend/

# move over project specific dependecy files
COPY ./pyproject.toml ./poetry.lock /

# Install poetry using pip
RUN . /backend/bin/activate && \
    pip install --no-cache --upgrade pip && \
    pipx install --no-cache --suffix _npm git+https://github.com/radoering/poetry.git@non-package-mode && \
    pip freeze | awk -F= '{print $1}' > /installed_pip_requirements.txt

# Install project dependencies using poetry
RUN . /backend/bin/activate && \
    poetry_npm config --no-cache virtualenvs.create false && \
    poetry_npm install --no-interaction --no-ansi --no-cache --only main && \
    poetry_npm export --without-hashes --only main --without-urls | awk -F= '{print $1}' > /installed_poetry_requirements.txt

# cleanup python dependencies that are not needed anymore
RUN . /backend/bin/activate && \
    grep -v -x -f /installed_poetry_requirements.txt /installed_pip_requirements.txt > /build_requirements.txt && \
    pip uninstall -y -r /build_requirements.txt 

COPY ./backend /backend

# Setup init script and config files
COPY ./docker/init_scripts/* /
COPY ./docker/nginx/default.conf /etc/nginx/nginx.conf

# cleanup additional build dependencies
RUN apk del \
        gcc \
        libffi-dev \
        mariadb-connector-c-dev \
        musl-dev \
        python3-dev \
        py3-pip

# cleanup leftover files that are not needed at runtime
RUN rm -r \
    /pyproject.toml \
    /poetry.lock \
    /installed_pip_requirements.txt \
    /installed_poetry_requirements.txt \
    /build_requirements.txt \
    /docker-entrypoint.sh \
    /docker-entrypoint.d

# Move everything we prepared over to our final docker image
FROM scratch
COPY --from=production-stage / /
RUN addgroup -g 1000 -S romm && adduser -u 1000 -D -S -G romm romm
RUN mkdir /romm && chown 1000:1000 /romm -R

# Expose ports and start
EXPOSE 8080
WORKDIR /romm
CMD ["/init"]
