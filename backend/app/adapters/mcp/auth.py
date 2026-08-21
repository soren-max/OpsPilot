from typing import Protocol

import jwt
from mcp.server.auth.middleware.auth_context import get_access_token
from mcp.server.auth.provider import AccessToken, TokenVerifier

from app.adapters.mcp.errors import McpUnauthorized


class McpTokenVerifier(Protocol):
    async def verify(self, token: str) -> AccessToken | None: ...


class SdkTokenVerifier(TokenVerifier):
    """Bridge to the official SDK auth boundary; issuer/audience validation stays pluggable."""

    def __init__(self, verifier: McpTokenVerifier) -> None:
        self.verifier = verifier

    async def verify_token(self, token: str) -> AccessToken | None:
        return await self.verifier.verify(token)


class JwtMcpTokenVerifier:
    """Resource-server verifier; token issuance remains outside OpsPilot M7."""

    def __init__(self, secret: str, issuer: str, audience: str) -> None:
        self.secret = secret
        self.issuer = issuer
        self.audience = audience

    async def verify(self, token: str) -> AccessToken | None:
        try:
            claims = jwt.decode(
                token,
                self.secret,
                algorithms=["HS256"],
                issuer=self.issuer,
                audience=self.audience,
                options={"require": ["exp", "iss", "aud", "sub"]},
            )
            raw_scope = claims.get("scope", "")
            scopes = raw_scope.split() if isinstance(raw_scope, str) else []
            return AccessToken(
                token=token,
                client_id=str(claims.get("client_id", claims["sub"])),
                subject=str(claims["sub"]),
                scopes=scopes,
                expires_at=int(claims["exp"]),
                resource=self.audience,
                claims={"iss": claims["iss"], "aud": claims["aud"]},
            )
        except (jwt.PyJWTError, KeyError, TypeError, ValueError):
            return None


def require_scope(scope: str) -> str:
    token = get_access_token()
    if token is None:
        return "local-stdio"
    if scope not in token.scopes:
        raise McpUnauthorized(f"MCP token requires {scope}")
    return token.subject or token.client_id
