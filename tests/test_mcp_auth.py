from fastapi.testclient import TestClient

from mcp_server.main import app


client = TestClient(app)


def test_mcp_post_requires_auth() -> None:
    response = client.post('/mcp', json={
        'jsonrpc': '2.0',
        'id': 1,
        'method': 'initialize',
        'params': {},
    })
    assert response.status_code == 401
