import datetime
import ssl
from pathlib import Path

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    pkcs7,
)
from cryptography.x509.oid import NameOID

from utils.tls import build_ca_ssl_context

HOSTNAME = "idp.example.test"


def _issue(
    subject: str,
    issuer: tuple[x509.Certificate, ec.EllipticCurvePrivateKey] | None,
    is_ca: bool,
) -> tuple[x509.Certificate, ec.EllipticCurvePrivateKey]:
    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, subject)])
    issuer_name, signing_key = (issuer[0].subject, issuer[1]) if issuer else (name, key)
    now = datetime.datetime.now(datetime.timezone.utc)
    builder = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(issuer_name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=1))
        .add_extension(x509.BasicConstraints(ca=is_ca, path_length=None), True)
        .add_extension(
            x509.SubjectKeyIdentifier.from_public_key(key.public_key()), False
        )
    )
    if issuer:
        builder = builder.add_extension(
            x509.AuthorityKeyIdentifier.from_issuer_public_key(issuer[1].public_key()),
            False,
        )
    if is_ca:
        builder = builder.add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            True,
        )
    else:
        builder = builder.add_extension(
            x509.SubjectAlternativeName([x509.DNSName(HOSTNAME)]), False
        ).add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]), False
        )
    return builder.sign(signing_key, hashes.SHA256()), key


@pytest.fixture
def pki(tmp_path: Path):
    """Offline root, an intermediate, and a leaf issued by the intermediate."""
    root = _issue("Test Root CA", None, is_ca=True)
    intermediate = _issue("Test Enterprise CA", root, is_ca=True)
    leaf = _issue(HOSTNAME, intermediate, is_ca=False)

    leaf_cert = tmp_path / "leaf.pem"
    leaf_cert.write_bytes(leaf[0].public_bytes(Encoding.PEM))
    leaf_key = tmp_path / "leaf.key"
    leaf_key.write_bytes(
        leaf[1].private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption())
    )
    return {
        "root": root[0],
        "intermediate": intermediate[0],
        "leaf_cert": leaf_cert,
        "leaf_key": leaf_key,
    }


def _handshake(client_ctx: ssl.SSLContext, pki) -> None:
    """Run a TLS handshake in memory against a server sending only its leaf."""
    server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server_ctx.load_cert_chain(pki["leaf_cert"], pki["leaf_key"])

    c_in, c_out, s_in, s_out = (ssl.MemoryBIO() for _ in range(4))
    client = client_ctx.wrap_bio(c_in, c_out, server_hostname=HOSTNAME)
    server = server_ctx.wrap_bio(s_in, s_out, server_side=True)

    client_done = server_done = False
    for _ in range(10):
        if not client_done:
            try:
                client.do_handshake()
                client_done = True
            except ssl.SSLWantReadError:
                pass
        s_in.write(c_out.read())
        if not server_done:
            try:
                server.do_handshake()
                server_done = True
            except ssl.SSLWantReadError:
                pass
        c_in.write(s_out.read())
        if client_done and server_done:
            return
    raise AssertionError("TLS handshake did not complete")


def _pem(*certs: x509.Certificate) -> bytes:
    return b"".join(c.public_bytes(Encoding.PEM) for c in certs)


def test_unset_path_returns_none():
    assert build_ca_ssl_context(None) is None
    assert build_ca_ssl_context("") is None


def test_pem_bundle_with_root_and_intermediate_verifies_leaf(tmp_path, pki):
    bundle = tmp_path / "fullchain.pem"
    bundle.write_bytes(_pem(pki["root"], pki["intermediate"]))

    ctx = build_ca_ssl_context(str(bundle))

    assert ctx is not None
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    assert ctx.check_hostname
    _handshake(ctx, pki)


def test_default_cas_are_kept_alongside_the_bundle(tmp_path, pki):
    bundle = tmp_path / "fullchain.pem"
    bundle.write_bytes(_pem(pki["root"], pki["intermediate"]))

    ctx = build_ca_ssl_context(str(bundle))

    assert ctx is not None
    assert ctx.cert_store_stats()["x509_ca"] > 2


def test_der_and_p7b_bundles_are_accepted(tmp_path, pki):
    (tmp_path / "root.crt").write_bytes(pki["root"].public_bytes(Encoding.DER))
    (tmp_path / "chain.p7b").write_bytes(
        pkcs7.serialize_certificates([pki["intermediate"]], Encoding.DER)
    )

    ctx = build_ca_ssl_context(str(tmp_path / "root.crt"))
    assert ctx is not None
    ctx.load_verify_locations(
        cadata=pki["intermediate"].public_bytes(Encoding.PEM).decode()
    )
    _handshake(ctx, pki)

    ctx = build_ca_ssl_context(str(tmp_path / "chain.p7b"))
    assert ctx is not None
    ctx.load_verify_locations(cadata=pki["root"].public_bytes(Encoding.PEM).decode())
    _handshake(ctx, pki)


def test_directory_loads_every_certificate_file(tmp_path, pki):
    certs_dir = tmp_path / "certs"
    certs_dir.mkdir()
    (certs_dir / "root.crt").write_bytes(pki["root"].public_bytes(Encoding.DER))
    (certs_dir / "intermediate.pem").write_bytes(_pem(pki["intermediate"]))
    (certs_dir / "notes.txt").write_text("not a certificate")

    ctx = build_ca_ssl_context(str(certs_dir))

    assert ctx is not None
    _handshake(ctx, pki)


def test_root_alone_cannot_verify_a_leaf_missing_its_intermediate(tmp_path, pki):
    bundle = tmp_path / "root.pem"
    bundle.write_bytes(_pem(pki["root"]))

    ctx = build_ca_ssl_context(str(bundle))

    assert ctx is not None
    with pytest.raises(ssl.SSLCertVerificationError):
        _handshake(ctx, pki)


def test_missing_path_still_verifies_with_default_cas(tmp_path, pki):
    ctx = build_ca_ssl_context(str(tmp_path / "missing.pem"))

    assert ctx is not None
    assert ctx.verify_mode == ssl.CERT_REQUIRED
    with pytest.raises(ssl.SSLCertVerificationError):
        _handshake(ctx, pki)
