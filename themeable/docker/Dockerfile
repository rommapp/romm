# syntax=docker/dockerfile:1
# RomM with the themeable module, built on a stock RomM release image.
# Build context is the repository root:
#
#   docker build -f themeable/docker/Dockerfile \
#     --build-arg ROMM_VERSION=<upstream tag> -t romm-themeable:<upstream tag> .
#
# The frontend is rebuilt from this branch's RomM source plus themeable/overlay and
# themeable/patches (the Branding tab); the backend gets the Branding router patched
# into the release image's own files. Theme packs are compiled when the container
# starts, from the built-in packs and the folder mapped at /romm/themes.
ARG ROMM_IMAGE=rommapp/romm
ARG ROMM_VERSION=latest
ARG NODE_IMAGE=node:24-alpine

FROM ${ROMM_IMAGE}:${ROMM_VERSION} AS romm

# The output is static JS/CSS, so it builds on the native platform like upstream's.
FROM --platform=$BUILDPLATFORM ${NODE_IMAGE} AS frontend
WORKDIR /src
COPY frontend/package*.json frontend/.npmrc frontend/
RUN cd frontend && npm ci --ignore-scripts --no-audit --no-fund
COPY frontend/ frontend/
COPY themeable/ themeable/
RUN node themeable/scripts/apply-source.mjs --root /src --only frontend --force \
 && cd frontend && npm run build

# The release image carries Node, so the module's build steps run there.
FROM romm AS module
WORKDIR /themeable
COPY themeable/ ./
COPY --from=frontend /src/frontend/dist /tmp/dist
RUN set -eu; \
    mkdir -p /out/catalog /out/hooks /out/src/backend; \
    cp catalog/token-aliases.json /out/catalog/; \
    (cd /var/www/html && find assets -type f) > /tmp/assets.txt; \
    node scripts/catalog.mjs --tokens /tmp/dist/assets --assets-list /tmp/assets.txt --no-src \
      --css-refs-from catalog/assets.json --out /out/catalog; \
    rm -rf catalog && cp -r /out/catalog catalog; \
    node scripts/build.mjs --out /tmp/check; \
    cp /backend/main.py /out/src/backend/main.py; \
    node scripts/apply-source.mjs --root /out/src --only backend --no-tests; \
    node scripts/apply-hooks.mjs --webroot /tmp/dist --nginx /etc/nginx/templates/default.conf.template --out /out/hooks; \
    rm -rf dist /tmp/check overlay patches test dev

FROM romm
ARG ROMM_VERSION
LABEL org.opencontainers.image.source="https://github.com/Stealthx3/romm-themeable" \
      org.opencontainers.image.description="RomM ${ROMM_VERSION} with the themeable theme module"
COPY --from=frontend /src/frontend/dist/ /var/www/html/
COPY --from=module /out/hooks/index.html /out/hooks/sw.js /var/www/html/
COPY --from=module /out/hooks/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=module /out/src/backend/ /backend/
COPY --from=module /themeable/ /themeable/
# Compiled themes live in a writable folder so the backend can rebuild them as any user;
# nginx reaches them through these links. Precompressed copies of the hooked files go,
# since nginx would prefer them over the hooked versions.
RUN set -eu; cd /var/www/html; \
    rm -f index.html.gz index.html.br sw.js.gz sw.js.br; \
    rm -rf themes themeable; \
    ln -s /tmp/themeable/current/themes themes; \
    ln -s /tmp/themeable/current/themeable themeable; \
    chmod +x /themeable/docker/entrypoint.sh
ENV THEMEABLE_HOME=/themeable \
    THEMEABLE_PACKS_PATH=/romm/themes \
    THEMEABLE_RUNTIME_DIR=/tmp/themeable
ENTRYPOINT ["/themeable/docker/entrypoint.sh"]
CMD ["/init"]
