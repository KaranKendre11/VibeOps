from __future__ import annotations

import io
import logging

import pytest

from vibeops.core.logging import RedactingFormatter


@pytest.fixture()
def logger_and_stream() -> tuple[logging.Logger, io.StringIO]:
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.setFormatter(RedactingFormatter("%(message)s"))
    log = logging.getLogger("test_redaction")
    log.handlers = [handler]
    log.setLevel(logging.DEBUG)
    log.propagate = False
    return log, stream


def _emit(log: logging.Logger, stream: io.StringIO, msg: str) -> str:
    log.info(msg)
    return stream.getvalue()


def test_openai_key_redacted(logger_and_stream: tuple[logging.Logger, io.StringIO]) -> None:
    log, stream = logger_and_stream
    out = _emit(log, stream, "key=sk-thisisafakekey1234567890abcdef")
    assert "sk-thisisafakekey1234567890abcdef" not in out
    assert "sk-***REDACTED***" in out


def test_pem_block_redacted(logger_and_stream: tuple[logging.Logger, io.StringIO]) -> None:
    log, stream = logger_and_stream
    pem = (
        "-----BEGIN RSA PRIVATE KEY-----\n"
        "MIIEowIBAAKCAQEA0Z3VS5JJcds3xHn/ygWep4\n"
        "-----END RSA PRIVATE KEY-----"
    )
    out = _emit(log, stream, f"creds={pem}")
    assert "MIIEowIBAAKCAQEA0Z3VS5JJcds3xHn" not in out
    assert "***PEM-REDACTED***" in out


def test_private_key_json_redacted(logger_and_stream: tuple[logging.Logger, io.StringIO]) -> None:
    log, stream = logger_and_stream
    out = _emit(log, stream, '"private_key": "supersecret"')
    assert "supersecret" not in out
    assert '"private_key": "***REDACTED***"' in out


def test_client_email_json_redacted(logger_and_stream: tuple[logging.Logger, io.StringIO]) -> None:
    log, stream = logger_and_stream
    out = _emit(log, stream, '"client_email": "sa@project.iam.gserviceaccount.com"')
    assert "sa@project.iam.gserviceaccount.com" not in out
    assert '"client_email": "***REDACTED***"' in out


def test_non_secret_content_passes_through(
    logger_and_stream: tuple[logging.Logger, io.StringIO],
) -> None:
    log, stream = logger_and_stream
    out = _emit(log, stream, "Deploying resource in us-central1")
    assert "Deploying resource in us-central1" in out
