# build frontend
FROM node:lts-alpine as front-build-stage
WORKDIR /front
COPY ./frontend/package*.json .
RUN npm install
COPY ./frontend .
RUN npm run build

# setup frontend
FROM ubuntu/nginx:1.18-22.04_edge as production-stage
ARG WEBSERVER_FOLDER=/var/www/html
COPY --from=front-build-stage /front/dist ${WEBSERVER_FOLDER}
COPY ./frontend/assets/platforms ${WEBSERVER_FOLDER}/assets/platforms
RUN mkdir -p ${WEBSERVER_FOLDER}/assets/romm && \
    ln -s /romm/library ${WEBSERVER_FOLDER}/assets/romm/library && \
    ln -s /romm/resources ${WEBSERVER_FOLDER}/assets/romm/resources

# setup backend
RUN apt update && \
    apt install -y --no-install-recommends ca-certificates curl gnupg && \
      # add deadsnakes ppa for Python versions
      echo "deb https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu jammy main" > /etc/apt/sources.list.d/deadsnakes-ubuntu-ppa-jammy.list && \
      apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F23C5A6CF475977595C89F51BA6932366A755776 && \
    apt update && \
    apt install -y --no-install-recommends \
      libmariadb3 libmariadb-dev gcc \
      python3.10 python3.10-dev python3-pip && \
    apt autoremove && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/*
WORKDIR /back
RUN pip install --no-cache --upgrade pip && \
    pip install --no-cache poetry && \
    poetry config virtualenvs.create false && \
    poetry install --no-dev --no-interaction --no-ansi
COPY ./backend .

# setup init script and config files
COPY ./docker/init_scripts/* /
COPY ./docker/nginx/default.conf /etc/nginx/nginx.conf

EXPOSE 80

WORKDIR /romm
CMD ["/init"]
