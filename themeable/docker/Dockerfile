# syntax=docker/dockerfile:1
# RomM with the themeable module layered on top of a stock release image.
# Build context is the themeable/ folder:
#
#   docker build -f themeable/docker/Dockerfile \
#     --build-arg ROMM_VERSION=<upstream tag> --build-arg THEMEABLE_DEFAULT=ember \
#     -t romm-themeable:<upstream tag> themeable
#
# Nothing upstream is rebuilt: packs are compiled against the CSS and artwork the
# image actually ships, and the hooks are applied to copies of its files.
ARG ROMM_IMAGE=rommapp/romm
ARG ROMM_VERSION=latest

FROM ${ROMM_IMAGE}:${ROMM_VERSION} AS romm

# The stock image already carries Node, so the build runs there with no extra base image.
FROM romm AS build
ARG THEMEABLE_DEFAULT=none
WORKDIR /themeable
COPY . .
RUN set -eu; \
    web=/var/www/html; \
    mkdir -p /out/catalog /out/hooks; \
    cp catalog/token-aliases.json /out/catalog/; \
    (cd "$web" && find assets -type f) > /out/assets.txt; \
    node scripts/catalog.mjs --tokens "$web/assets" --assets-list /out/assets.txt --no-src --out /out/catalog; \
    node scripts/build.mjs --catalog /out/catalog --out /out/web --default "$THEMEABLE_DEFAULT"; \
    mkdir -p /out/web/root; \
    (cd /out/web/root && find . -type f | sed 's#^\./##') > /out/root-files.txt; \
    node scripts/apply-hooks.mjs --webroot "$web" --nginx /etc/nginx/templates/default.conf.template \
      --root-overlay /out/web/root --out /out/hooks --default "$THEMEABLE_DEFAULT"

FROM romm
ARG ROMM_VERSION
ARG THEMEABLE_DEFAULT=none
LABEL org.opencontainers.image.source="https://github.com/Stealthx3/romm-themeable" \
      org.opencontainers.image.description="RomM ${ROMM_VERSION} with the themeable theme module" \
      io.romm-themeable.default-theme="${THEMEABLE_DEFAULT}"
COPY --from=build /out/web/themes /var/www/html/themes
COPY --from=build /out/web/themeable /var/www/html/themeable
COPY --from=build /out/web/root/ /var/www/html/
COPY --from=build /out/hooks/index.html /out/hooks/sw.js /var/www/html/
COPY --from=build /out/hooks/default.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /out/root-files.txt /tmp/themeable-root-files.txt
# nginx prefers precompressed siblings, which still hold the stock content.
RUN set -eu; cd /var/www/html; \
    for f in index.html sw.js $(cat /tmp/themeable-root-files.txt); do rm -f "$f.gz" "$f.br"; done; \
    rm /tmp/themeable-root-files.txt
