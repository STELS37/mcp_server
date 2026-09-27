import asyncio
import io
import json
import urllib.error
import urllib.request

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


def test_http_probe_returns_structured_http_error(monkeypatch) -> None:
    def fake_urlopen(request, *, timeout, context):
        assert request.full_url == 'http://127.0.0.1:8000/definitely-missing'
        assert timeout == 2
        raise urllib.error.HTTPError(
            request.full_url,
            404,
            'Not Found',
            {},
            io.BytesIO(b'missing'),
        )

    monkeypatch.setattr(urllib.request, 'urlopen', fake_urlopen)

    tools = MCPTools(None)
    result = asyncio.run(
        tools.execute_tool(
            'http_probe',
            {'path': '/definitely-missing', 'headers': {'X-Test': '1'}, 'timeout': 2},
            user='test',
        )
    )

    assert result['isError'] is True
    payload = json.loads(result['content'][0]['text'])
    assert payload == {
        'success': False,
        'url': 'http://127.0.0.1:8000/definitely-missing',
        'status_code': 404,
        'headers': {},
        'body': 'missing',
        'truncated': False,
    }


def test_service_control_status_returns_structured_payload(monkeypatch) -> None:
    class FakeProcess:
        returncode = 0

        async def communicate(self):
            return b'active (running)\n', b''

        def kill(self):
            raise AssertionError('kill must not be called on a successful status probe')

    async def fake_create_subprocess_exec(*cmd, **kwargs):
        assert cmd == ('systemctl', 'status', 'mcp-server')
        assert kwargs['stdout'] is asyncio.subprocess.PIPE
        assert kwargs['stderr'] is asyncio.subprocess.PIPE
        return FakeProcess()

    monkeypatch.setattr(asyncio, 'create_subprocess_exec', fake_create_subprocess_exec)

    tools = MCPTools(None)
    result = asyncio.run(
        tools.execute_tool(
            'service_control',
            {'service': 'mcp-server', 'action': 'status', 'timeout': 5},
            user='test',
        )
    )

    assert result['isError'] is False
    payload = json.loads(result['content'][0]['text'])
    assert payload == {
        'success': True,
        'action': 'status',
        'service': 'mcp-server',
        'exit_code': 0,
        'output': 'active (running)\n',
        'error': '',
        'mode': 'sync',
    }
