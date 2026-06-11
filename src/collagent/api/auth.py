import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

from collagent.config import settings

_bearer = HTTPBearer(auto_error=False)

# Supabase signs user access tokens with asymmetric JWT signing keys (ES256/RS256)
# when they are enabled, serving the public keys at the project's JWKS endpoint.
# Projects on the legacy shared secret (and our tests) sign with HS256 instead, so
# we accept both: pick the verification path from the token's `alg` header.
_ASYMMETRIC_ALGS = ("ES256", "RS256")
_jwks_client: PyJWKClient | None = None


def _get_jwks_client() -> PyJWKClient:
    global _jwks_client
    if _jwks_client is None:
        _jwks_client = PyJWKClient(
            f"{settings.supabase_url}/auth/v1/.well-known/jwks.json"
        )
    return _jwks_client


def get_current_user_id(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str:
    if creds is None:
        raise HTTPException(status_code=401, detail="Missing bearer token")
    token = creds.credentials
    try:
        alg = jwt.get_unverified_header(token).get("alg")
        if alg in _ASYMMETRIC_ALGS:
            key = _get_jwks_client().get_signing_key_from_jwt(token).key
            algorithms = list(_ASYMMETRIC_ALGS)
        else:
            key = settings.supabase_jwt_secret
            algorithms = ["HS256"]
        payload = jwt.decode(
            token,
            key,
            algorithms=algorithms,
            audience="authenticated",
        )
    except jwt.PyJWTError as exc:
        raise HTTPException(status_code=401, detail=f"Invalid token: {exc}")
    return payload["sub"]
