from fastapi.testclient import TestClient

from mcp_server.main import app


def test_mcp_discovery_returns_tools() -> None:
    with TestClient(app) as client:
        response = client.get('/mcp')
        assert response.status_code == 200
        body = response.json()
        assert 'result' in body
        assert 'tools' in body['result']
        assert isinstance(body['result']['tools'], list)
        assert any(tool.get('name') == 'system_status' for tool in body['result']['tools'])
