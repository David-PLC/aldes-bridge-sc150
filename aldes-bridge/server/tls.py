"""Generazione certificato TLS self-signed per aldesiotsuite.azure-devices.net."""
import os
import ssl
import tempfile
from datetime import datetime, timedelta, timezone

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _generate_cert(common_name):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, common_name)])
    now = datetime.now(timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=3650))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(common_name)]), critical=False)
        .sign(key, hashes.SHA256())
    )
    cert_fd, cert_path = tempfile.mkstemp(prefix="aldes_crt_", suffix=".pem")
    key_fd, key_path = tempfile.mkstemp(prefix="aldes_key_", suffix=".pem")
    with os.fdopen(cert_fd, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    with os.fdopen(key_fd, "wb") as f:
        f.write(key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        ))
    return cert_path, key_path


def server_context(common_name="aldesiotsuite.azure-devices.net"):
    cert_path, key_path = _generate_cert(common_name)
    try:
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        ctx.load_cert_chain(cert_path, key_path)
    finally:
        for p in (cert_path, key_path):
            try:
                os.unlink(p)
            except OSError:
                pass
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    try:
        ctx.minimum_version = ssl.TLSVersion.TLSv1
    except Exception:
        pass
    try:
        ctx.set_ciphers("ALL:@SECLEVEL=0")
    except ssl.SSLError:
        pass
    return ctx