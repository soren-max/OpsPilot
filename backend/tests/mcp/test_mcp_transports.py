import asyncio
import socket
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx2
import jwt
from mcp import Client, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client

from app.adapters.mcp.contracts import MCP_PROTOCOL_VERSION

FIXTURE = Path(__file__).with_name("interop_fixture.py")
SECRET = "mcp-interop-secret-key-at-least-32-characters"
ISSUER = "https://issuer.opspilot.test"
AUDIENCE = "http://127.0.0.1:18110/mcp"


async def _health(client: Client) -> None:
    result = await client.call_tool(
        "get_service_health",
        {"request": {"service": "web", "environment": "test"}},
    )
    assert result.structured_content is not None
    assert result.structured_content["data"]["status"] == "HEALTHY"


def test_stdio_official_client_black_box() -> None:
    params = StdioServerParameters(command=sys.executable, args=[str(FIXTURE), "stdio"])

    async def run() -> None:
        async with Client(stdio_client(params), mode=MCP_PROTOCOL_VERSION) as client:
            await _health(client)

    asyncio.run(run())


def test_stateless_streamable_http_auth_and_official_client() -> None:
    process = subprocess.Popen(
        [sys.executable, str(FIXTURE), "http"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(50):
            try:
                with socket.create_connection(("127.0.0.1", 18110), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.1)
        else:
            raise AssertionError("MCP HTTP fixture did not start")
        time.sleep(0.5)
        with httpx2.Client(trust_env=False) as raw_client:
            unauthorized = raw_client.post(
                AUDIENCE,
                json={},
                headers={"MCP-Protocol-Version": MCP_PROTOCOL_VERSION},
                timeout=2,
            )
        assert unauthorized.status_code == 401
        token = jwt.encode(
            {
                "iss": ISSUER,
                "aud": AUDIENCE,
                "sub": "interop-client",
                "scope": "opspilot.observe",
                "exp": datetime.now(UTC) + timedelta(minutes=5),
            },
            SECRET,
            algorithm="HS256",
        )

        async def run() -> None:
            http = httpx2.AsyncClient(headers={"Authorization": f"Bearer {token}"}, trust_env=False)
            async with http:
                transport = streamable_http_client(AUDIENCE, http_client=http)
                async with Client(transport, mode=MCP_PROTOCOL_VERSION) as client:
                    await _health(client)

        asyncio.run(run())
    finally:
        process.terminate()
        process.wait(timeout=10)
