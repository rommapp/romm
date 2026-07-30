ARG ALPINE_VERSION=3.23
ARG ALPINE_SHA256=25109184c71bdad752c8312a8623239686a9a2071e8825f20acb8f2198c3f659

FROM alpine:${ALPINE_VERSION}@sha256:${ALPINE_SHA256}

ARG SAMBA_VERSION=4.22.10-r0

RUN apk add --no-cache \
    python3=3.12.13-r0 \
    samba-client=${SAMBA_VERSION} \
    samba-common-tools=${SAMBA_VERSION} \
    samba-server=${SAMBA_VERSION} && \
    addgroup -g 1000 -S romm && \
    adduser -u 1000 -D -H -S -G romm -s /sbin/nologin romm

COPY --chmod=644 docker/smb/smb.conf.template /etc/samba/smb.conf.template
COPY --chmod=755 docker/smb/controller.py /usr/local/bin/smb-controller
COPY --chmod=755 docker/smb/healthcheck.sh /usr/local/bin/smb-healthcheck

EXPOSE 445/tcp

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD ["/usr/local/bin/smb-healthcheck"]

ENTRYPOINT ["/usr/local/bin/smb-controller"]
