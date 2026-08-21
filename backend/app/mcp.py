import argparse

from mcp.server.auth.settings import AuthSettings

from app.adapters.mcp.application import (
    IncidentMcpResourceReader,
    WorkflowGovernedActionProposer,
)
from app.adapters.mcp.auth import JwtMcpTokenVerifier, SdkTokenVerifier
from app.adapters.mcp.broker import McpCapabilityBroker
from app.adapters.mcp.server import build_mcp_server
from app.application.workflow_service import WorkflowService
from app.core.config import get_settings
from app.db.session import SessionLocal
from app.memory.factory import build_memory_store
from app.worker import (
    build_action_service,
    build_incident_capabilities,
    build_investigator,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="OpsPilot MCP capability plane")
    parser.add_argument("transport", choices=("stdio", "http"), default="stdio", nargs="?")
    args = parser.parse_args()
    settings = get_settings()
    with SessionLocal() as db:
        action_service = build_action_service(db, settings)
        capabilities = build_incident_capabilities(db, settings, action_service)
        memory = build_memory_store(settings)
        workflow = WorkflowService(
            db,
            investigator=build_investigator(settings),
            action_service=action_service,
            capabilities=capabilities,
            knowledge_retriever=memory,
        )
        broker = McpCapabilityBroker(
            capabilities.policy,
            metrics=capabilities.metrics,
            logs=capabilities.logs,
            tickets=capabilities.tickets,
            health=capabilities.health,
            knowledge=memory,
            action_proposer=WorkflowGovernedActionProposer(db, workflow, action_service),
            timeout_seconds=settings.capability_timeout_seconds,
        )
        if args.transport == "stdio":
            build_mcp_server(broker, IncidentMcpResourceReader(db)).run("stdio")
            return
        if not settings.mcp_auth_issuer or not settings.mcp_auth_audience:
            parser.error("HTTP requires OPSPILOT_MCP_AUTH_ISSUER and OPSPILOT_MCP_AUTH_AUDIENCE")
        verifier = SdkTokenVerifier(
            JwtMcpTokenVerifier(
                settings.secret_key,
                settings.mcp_auth_issuer,
                settings.mcp_auth_audience,
            )
        )
        auth = AuthSettings.model_validate(
            {
                "issuer_url": settings.mcp_auth_issuer,
                "resource_server_url": settings.mcp_auth_audience,
                "required_scopes": [],
            }
        )
        build_mcp_server(
            broker,
            IncidentMcpResourceReader(db),
            token_verifier=verifier,
            auth_settings=auth,
        ).run(
            "streamable-http",
            host=settings.mcp_http_host,
            port=settings.mcp_http_port,
            stateless_http=True,
            json_response=True,
        )


if __name__ == "__main__":
    main()
