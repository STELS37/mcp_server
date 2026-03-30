"""Unix-socket client for the local privileged MCP broker."""
import asyncio
import json
from pathlib import Path
from typing import Any, Dict

BROKER_SOCK = Path('/run/mcp-brokerd.sock')


class BrokerClientError(RuntimeError):
    pass


async def broker_request(method: str, params: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
    if not BROKER_SOCK.exists():
        raise BrokerClientError(f'broker socket not found: {BROKER_SOCK}')
    reader, writer = await asyncio.wait_for(asyncio.open_unix_connection(str(BROKER_SOCK)), timeout=timeout)
    try:
        payload = {'method': method, 'params': params}
        writer.write((json.dumps(payload, ensure_ascii=False) + '\n').encode())
        await writer.drain()
        line = await asyncio.wait_for(reader.readline(), timeout=timeout)
        if not line:
            raise BrokerClientError('empty response from broker')
        resp = json.loads(line.decode())
        if not isinstance(resp, dict):
            raise BrokerClientError('invalid broker response shape')
        return resp
    finally:
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass

