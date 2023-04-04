# build frontend
FROM node:lts-alpine as front-build-stage
WORKDIR /front
COPY ./frontend/package*.json ./
RUN npm install
COPY ./frontend ./
RUN npm run build

# setup frontend
FROM ubuntu/nginx:1.18-22.04_edge as production-stage
COPY --from=front-build-stage /front/dist /var/www/html
COPY ./frontend/assets/platforms /var/www/html/assets/platforms
RUN mkdir -p /var/www/html/assets/romm
RUN ln -s /romm/library /var/www/html/assets/romm/library
RUN ln -s /romm/resources /var/www/html/assets/romm/resources

# setup backend
RUN apt update 
RUN apt install -y software-properties-common gcc 
RUN add-apt-repository -y ppa:deadsnakes/ppa
RUN apt update -y && apt install libmariadb3 libmariadb-dev -y
RUN apt install -y python3.10 python3-pip
WORKDIR /back
COPY ./backend/requirements.txt ./requirements.txt
RUN pip install --upgrade pip
RUN pip install --no-cache-dir --upgrade -r ./requirements.txt
COPY ./backend/src ./

# setup init script and config files
COPY ./docker/init_scripts/init_back /init_back
COPY ./docker/init_scripts/init_front /init_front
COPY ./docker/init_scripts/init /init
COPY ./docker/nginx/default.conf /etc/nginx/nginx.conf

EXPOSE 80

CMD ["/init"]
