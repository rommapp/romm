# syntax=docker/dockerfile:1
# RomM with the themeable module on a stock release image; build from the repository root.
# How the stages fit together: themeable/README.md#how-it-works
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
    node scripts/zip-packs.mjs --packs packs --out /tmp/packs; \
    rm -rf packs && mv /tmp/packs packs; \
    cp /backend/main.py /out/src/backend/main.py; \
    node scripts/apply-source.mjs --root /out/src --only backend --no-tests; \
    node scripts/apply-hooks.mjs --webroot /tmp/dist --nginx /etc/nginx/templates/default.conf.template --out /out/hooks; \
    rm -rf dist /tmp/check overlay patches test dev

FROM romm
ARG ROMM_VERSION
ARG THEMEABLE_VERSION=dev
LABEL org.opencontainers.image.source="https://github.com/Stealthx3/romm-themeable" \
      org.opencontainers.image.version="${THEMEABLE_VERSION}-${ROMM_VERSION}" \
      org.opencontainers.image.description="RomM ${ROMM_VERSION} with the themeable theme module ${THEMEABLE_VERSION}"
COPY --from=frontend /src/frontend/dist/ /var/www/html/
COPY --from=module /out/hooks/index.html /out/hooks/sw.js /var/www/html/
COPY --from=module /out/hooks/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=module /out/src/backend/ /backend/
COPY --from=module /themeable/ /themeable/
# nginx reaches the writable compiled themes through these links, and would prefer the
# precompressed stock copies over the hooked files, so those go.
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
