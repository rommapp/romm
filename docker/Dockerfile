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
    apt install -y --no-install-recommends software-properties-common gnupg gcc && \
    add-apt-repository -y ppa:deadsnakes/ppa && \
    apt update -y && apt install --no-install-recommends libmariadb3 libmariadb-dev -y && \
    apt install -y --no-install-recommends python3.10 python3.10-dev python3-pip && \
    apt autoremove && \
    rm -rf /var/lib/apt/lists/* /var/cache/apt/*
WORKDIR /back
COPY ./backend/requirements.txt ./requirements.txt
RUN pip install --no-cache --upgrade pip && \
    pip install --no-cache --upgrade -r requirements.txt
COPY ./backend/src .

# setup init script and config files
COPY ./docker/init_scripts/* /
COPY ./docker/nginx/default.conf /etc/nginx/nginx.conf

EXPOSE 80

WORKDIR /romm
CMD ["/init"]
