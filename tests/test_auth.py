import time

import jwt
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from collagent.api import auth

SECRET = "test-secret"


def _token(sub="user-123", aud="authenticated", exp_offset=3600, secret=SECRET):
    return jwt.encode(
        {"sub": sub, "aud": aud, "exp": int(time.time()) + exp_offset},
        secret,
        algorithm="HS256",
    )


def _creds(token: str) -> HTTPAuthorizationCredentials:
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


@pytest.fixture(autouse=True)
def _secret(monkeypatch):
    monkeypatch.setattr(auth.settings, "supabase_jwt_secret", SECRET)


def test_valid_token_returns_user_id():
    assert auth.get_current_user_id(_creds(_token())) == "user-123"


def test_missing_token_401():
    with pytest.raises(HTTPException) as e:
        auth.get_current_user_id(None)
    assert e.value.status_code == 401


def test_bad_signature_401():
    with pytest.raises(HTTPException) as e:
        auth.get_current_user_id(_creds(_token(secret="wrong")))
    assert e.value.status_code == 401


def test_expired_token_401():
    with pytest.raises(HTTPException) as e:
        auth.get_current_user_id(_creds(_token(exp_offset=-100)))
    assert e.value.status_code == 401


def test_es256_token_verified_via_jwks(monkeypatch):
    # Real Supabase access tokens are ES256-signed; verify them via the JWKS key
    # (here a stubbed signing key) rather than the HS256 shared secret.
    from cryptography.hazmat.primitives.asymmetric import ec

    private_key = ec.generate_private_key(ec.SECP256R1())
    token = jwt.encode(
        {"sub": "user-es", "aud": "authenticated", "exp": int(time.time()) + 3600},
        private_key,
        algorithm="ES256",
    )

    class _Signing:
        key = private_key.public_key()

    class _Client:
        def get_signing_key_from_jwt(self, _token):
            return _Signing()

    monkeypatch.setattr(auth, "_get_jwks_client", lambda: _Client())
    assert auth.get_current_user_id(_creds(token)) == "user-es"
