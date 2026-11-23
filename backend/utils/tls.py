import ssl
from pathlib import Path

import certifi
from cryptography import x509
from cryptography.hazmat.primitives.serialization import Encoding, pkcs7

from logger.formatter import highlight as hl
from logger.logger import log


def _parse_certificates(data: bytes) -> list[x509.Certificate]:
    """Read every certificate from PEM, DER, or PKCS#7 (.p7b) bytes."""
    loaders = (
        x509.load_pem_x509_certificates,
        lambda d: [x509.load_der_x509_certificate(d)],
        pkcs7.load_pem_pkcs7_certificates,
        pkcs7.load_der_pkcs7_certificates,
    )
    for loader in loaders:
        try:
            return loader(data)
        except ValueError:
            continue
    return []


def build_ca_ssl_context(ca_path: str | None) -> ssl.SSLContext | None:
    """Build a context trusting the default CAs plus the certificates at `ca_path`.

    Args:
        ca_path: A certificate bundle file, or a directory of certificate files.

    Returns:
        The SSL context, or None when `ca_path` is unset.
    """
    if not ca_path:
        return None

    path = Path(ca_path)
    if path.is_dir():
        files = sorted(p for p in path.iterdir() if p.is_file())
    elif path.is_file():
        files = [path]
    else:
        log.error(f"CA certificate path {hl(ca_path)} does not exist")
        files = []

    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.load_default_certs()
    for file in files:
        try:
            data = file.read_bytes()
        except OSError as exc:
            log.error(f"Cannot read CA certificate file {hl(str(file))}: {exc}")
            continue
        certs = _parse_certificates(data)
        if not certs:
            log.warning(f"No certificates found in {hl(str(file))}")
            continue
        ctx.load_verify_locations(
            cadata="".join(c.public_bytes(Encoding.PEM).decode() for c in certs)
        )
    return ctx
