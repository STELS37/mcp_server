import asyncio

from fastapi.testclient import TestClient

from mcp_server.main import app
from mcp_server.tools.mcp_tools import MCPTools


client = TestClient(app)


def test_health_endpoint_returns_200() -> None:
    response = client.get('/health')
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'healthy'
    assert 'version' in body


def test_ready_endpoint_shape() -> None:
    response = client.get('/ready')
    assert response.status_code in (200, 503)
    body = response.json()
    assert 'ready' in body
    assert 'checks' in body


def test_control_health_endpoint_shape() -> None:
    response = client.get('/control-health')
    assert response.status_code in (200, 503)
    body = response.json()
    assert 'status' in body
    assert 'checks' in body


def test_http_probe_returns_structured_error_payload() -> None:
    tools = MCPTools(None)
    result = asyncio.run(
        tools.execute_tool(
            'http_probe',
            {'path': '/definitely-missing', 'headers': {'X-Test': '1'}, 'timeout': 2},
            user='test',
        )
    )
    assert result['isError'] is True
    text = result['content'][0]['text']
    assert '"status_code": 404' in text
    assert '"success": false' in text


def test_service_control_status_returns_structured_payload() -> None:
    tools = MCPTools(None)
    result = asyncio.run(
        tools.execute_tool(
            'service_control',
            {'service': 'mcp-server', 'action': 'status', 'timeout': 5},
            user='test',
        )
    )
    assert result['isError'] is False
    text = result['content'][0]['text']
    assert '"service": "mcp-server"' in text
    assert '"action": "status"' in text
