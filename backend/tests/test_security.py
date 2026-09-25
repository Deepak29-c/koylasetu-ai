import uuid

import jwt
import pytest

from app.core.security import create_token, decode_token, hash_password, verify_password


def test_password_hash_roundtrip():
    h = hash_password("s3cret")
    assert h != "s3cret"
    assert verify_password("s3cret", h)
    assert not verify_password("wrong", h)
    assert not verify_password("s3cret", "not-a-hash")


def test_token_roundtrip():
    uid = uuid.uuid4()
    assert decode_token(create_token(uid, "access"), "access") == uid


def test_refresh_token_is_not_an_access_token():
    token = create_token(uuid.uuid4(), "refresh")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token, "access")


def test_tampered_token_rejected():
    token = create_token(uuid.uuid4(), "access")
    with pytest.raises(jwt.InvalidTokenError):
        decode_token(token[:-2] + ("A" if token[-2] != "A" else "B") + token[-1], "access")
