import argparse
from datetime import UTC, datetime

from mcp.server.auth.settings import AuthSettings

from app.adapters.mcp.auth import JwtMcpTokenVerifier, SdkTokenVerifier
from app.adapters.mcp.broker import McpCapabilityBroker
from app.adapters.mcp.server import build_mcp_server
from app.capabilities.health import HealthObservation, HealthQuery, HealthStatus
from app.capabilities.policy import CapabilityQueryPolicy

SECRET = "mcp-interop-secret-key-at-least-32-characters"
ISSUER = "https://issuer.opspilot.test"
AUDIENCE = "http://127.0.0.1:18110/mcp"


class Health:
    async def get_service_health(self, query: HealthQuery) -> HealthObservation:
        now = datetime.now(UTC)
        return HealthObservation(
            service=query.service,
            environment=query.environment,
            status=HealthStatus.HEALTHY,
            summary="healthy",
            source_reference="fixture://health",
            observed_at=now,
            collected_at=now,
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("transport", choices=("stdio", "http"))
    args = parser.parse_args()
    broker = McpCapabilityBroker(CapabilityQueryPolicy(frozenset({"web"})), health=Health())
    if args.transport == "stdio":
        build_mcp_server(broker).run("stdio")
        return
    verifier = SdkTokenVerifier(JwtMcpTokenVerifier(SECRET, ISSUER, AUDIENCE))
    auth = AuthSettings.model_validate(
        {"issuer_url": ISSUER, "resource_server_url": AUDIENCE, "required_scopes": []}
    )
    build_mcp_server(broker, token_verifier=verifier, auth_settings=auth).run(
        "streamable-http",
        host="127.0.0.1",
        port=18110,
        stateless_http=True,
        json_response=True,
    )


if __name__ == "__main__":
    main()
