# Build frontend
FROM node:lts-alpine as front-build-stage
WORKDIR /front
COPY ./frontend ./
RUN npm install
RUN npm run build

# Setup frontend
FROM nginx:1.25.4-alpine3.18-slim as production-stage
ARG WEBSERVER_FOLDER=/var/www/html
COPY --from=front-build-stage /front/dist ${WEBSERVER_FOLDER}
COPY ./frontend/assets/default ${WEBSERVER_FOLDER}/assets/default
COPY ./frontend/assets/platforms ${WEBSERVER_FOLDER}/assets/platforms
COPY ./frontend/assets/webrcade/feed ${WEBSERVER_FOLDER}/assets/webrcade/feed
RUN mkdir -p ${WEBSERVER_FOLDER}/assets/romm && \
    ln -s /romm/resources ${WEBSERVER_FOLDER}/assets/romm/resources && \
    ln -s /romm/assets ${WEBSERVER_FOLDER}/assets/romm/assets

# # install generall required packages
RUN apk add --upgrade \
        bash \
        curl \
        libffi \
        # mariadb-connector-c \
        netcat-openbsd \
        # python3 \
        tzdata

# # Install additional build dependencies
# RUN apk add --upgrade \
#         gcc \
#         libffi-dev \
#         mariadb-connector-c-dev \
#         musl-dev \
#         python3-dev \
#         py3-pip \
#         git \
#         wget \
#         coreutils \
#         dpkg-dev dpkg \
#         linux-headers \
#         make \
#         openssl-dev

# Create python venv to not clash with OS python packages
# RUN python3 -m venv /backend/

# move over project specific dependecy files
# COPY ./pyproject.toml ./poetry.lock /

# Install poetry using pip
# RUN . /backend/bin/activate && \
#     pip install --no-cache --upgrade pip && \
#     pip install --no-cache git+https://github.com/radoering/poetry.git@non-package-mode && \
#     pip freeze | awk -F= '{print $1}' > /installed_pip_requirements.txt

# Install project dependencies using poetry
# RUN . /backend/bin/activate && \
#     mkdir -p /root/.cache/pypoetry/virtualenvs && \
#     python3 -m poetry config --no-cache virtualenvs.create false && \
#     python3 -m poetry env use 3.11 && \
#     python3 -m poetry install --no-interaction --no-ansi --no-cache --only main && \
#     python3 -m poetry export --without-hashes --only main --without-urls | awk -F= '{print $1}' > /installed_poetry_requirements.txt

# cleanup python dependencies that are not needed anymore
# RUN . /backend/bin/activate && \
#     grep -v -x -f /installed_poetry_requirements.txt /installed_pip_requirements.txt > /build_requirements.txt && \
#     pip uninstall -y -r /build_requirements.txt

# COPY ./backend /backend

# Setup init script and config files
COPY ./docker/init_scripts/* /
COPY ./docker/nginx/default.conf /etc/nginx/nginx.conf

# Install redis
# ENV REDIS_VERSION 7.2.4
# ENV REDIS_DOWNLOAD_URL http://download.redis.io/releases/redis-7.2.4.tar.gz
# ENV REDIS_DOWNLOAD_SHA 8d104c26a154b29fd67d6568b4f375212212ad41e0c2caa3d66480e78dbd3b59

# RUN wget -O redis.tar.gz "$REDIS_DOWNLOAD_URL"; \
# 	echo "$REDIS_DOWNLOAD_SHA *redis.tar.gz" | sha256sum -c -; \
# 	mkdir -p /usr/src/redis; \
# 	tar -xzf redis.tar.gz -C /usr/src/redis --strip-components=1; \
# 	rm redis.tar.gz; \
#     # disable Redis protected mode as it is unnecessary in context of Docker
#     # (ports are not automatically exposed when running inside Docker, but rather explicitly by specifying -p / -P)
# 	grep -E '^ *createBoolConfig[(]"protected-mode",.*, *1 *,.*[)],$' /usr/src/redis/src/config.c; \
# 	sed -ri 's!^( *createBoolConfig[(]"protected-mode",.*, *)1( *,.*[)],)$!\10\2!' /usr/src/redis/src/config.c; \
# 	grep -E '^ *createBoolConfig[(]"protected-mode",.*, *0 *,.*[)],$' /usr/src/redis/src/config.c; \
#     # for future reference, we modify this directly in the source instead of just supplying a default configuration flag because apparently "if you specify any argument to redis-server, [it assumes] you are going to specify everything"
#     # (more exactly, this makes sure the default behavior of "save on SIGTERM" stays functional by default)
# 	# (also, we do cross-builds, so we need to embed the appropriate "--build=xxx" values to that "./configure" invocation)
#     gnuArch="$(dpkg-architecture --query DEB_BUILD_GNU_TYPE)"; \
# 	extraJemallocConfigureFlags="--build=$gnuArch"; \
# 	dpkgArch="$(dpkg --print-architecture)"; \
#     case "${dpkgArch##*-}" in (amd64 | i386 | x32) extraJemallocConfigureFlags="$extraJemallocConfigureFlags --with-lg-page=12";; (*) extraJemallocConfigureFlags="$extraJemallocConfigureFlags --with-lg-page=16";; esac; \
# 	extraJemallocConfigureFlags="$extraJemallocConfigureFlags --with-lg-hugepage=21"; \
# 	grep -F 'cd jemalloc && ./configure ' /usr/src/redis/deps/Makefile; \
# 	sed -ri 's!cd jemalloc && ./configure !&'"$extraJemallocConfigureFlags"' !' /usr/src/redis/deps/Makefile; \
# 	grep -F "cd jemalloc && ./configure $extraJemallocConfigureFlags " /usr/src/redis/deps/Makefile; \
# 	export BUILD_TLS=yes; \
# 	make -C /usr/src/redis -j "$(nproc)" all; \
# 	make -C /usr/src/redis install; \
# 	serverMd5="$(md5sum /usr/local/bin/redis-server | cut -d' ' -f1)"; export serverMd5; \
# 	find /usr/local/bin/redis* -maxdepth 0 \
# 		-type f -not -name redis-server \
# 		-exec sh -eux -c ' \
# 			md5="$(md5sum "$1" | cut -d" " -f1)"; \
# 			test "$md5" = "$serverMd5"; \
# 		' -- '{}' ';' \
# 		-exec ln -svfT 'redis-server' '{}' ';' \
# 	; \
# 	rm -r /usr/src/redis; \
# 	runDeps="$( \
# 		scanelf --needed --nobanner --format '%n#p' --recursive /usr/local \
# 			| tr ',' '\n' \
# 			| sort -u \
# 			| awk 'system("[ -e /usr/local/lib/" $1 " ]") == 0 { next } { print "so:" $1 }' \
# 	)"; \
# 	apk add --no-network --virtual .redis-rundeps $runDeps; \
# 	apk del --no-network .build-deps; \
# 	redis-cli --version; \
# 	redis-server --version; \
# 	echo '{"spdxVersion":"SPDX-2.3","SPDXID":"SPDXRef-DOCUMENT","name":"redis-server-sbom","packages":[{"name":"redis-server","versionInfo":"7.2.4","SPDXID":"SPDXRef-Package--redis-server","externalRefs":[{"referenceCategory":"PACKAGE-MANAGER","referenceType":"purl","referenceLocator":"pkg:generic/redis-server@7.2.4?os_name=alpine&os_version=3.19"}],"licenseDeclared":"BSD-3-Clause"}]}' > /usr/local/redis.spdx.json

# # cleanup additional build dependencies
# RUN apk del \
#         gcc \
#         libffi-dev \
#         mariadb-connector-c-dev \
#         musl-dev \
#         python3-dev \
#         py3-pip \
#         git \
#         wget \
#         coreutils \
#         dpkg-dev dpkg \
#         linux-headers \
#         make \
#         openssl-dev

# cleanup leftover files that are not needed at runtime
RUN rm -r \
    /docker-entrypoint.sh \
    /docker-entrypoint.d

# User permissions
RUN addgroup -g 1000 -S romm && adduser -u 1000 -D -S -G romm romm

# Create the directories and set ownership and permissions
RUN mkdir /romm && chown romm:romm /romm

# Move everything we prepared over to our final docker image
FROM scratch
COPY --from=production-stage / /

# Declare the supported volumes
VOLUME ["/romm/resources", "/romm/assets"]

# Expose ports and start
EXPOSE 8080
WORKDIR /romm
CMD ["/init"]
