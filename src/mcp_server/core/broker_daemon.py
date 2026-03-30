"""Privileged local broker daemon for orchestrator control over a Unix socket."""
import asyncio
import json
import os
from pathlib import Path
from typing import Any, Dict

from mcp_server.core.task_orchestrator import (
    create_task,
    find_task,
    list_tasks,
    cancel_task,
    retry_task,
    task_log_path,
    get_worker_status,
    set_queue_paused,
)

BROKER_SOCK = Path('/run/mcp-brokerd.sock')


def _ok(result: Any) -> Dict[str, Any]:
    return {'ok': True, 'result': result}


def _err(message: str) -> Dict[str, Any]:
    return {'ok': False, 'error': message}


def _tail_log(task_id: str, lines: int) -> Dict[str, Any]:
    path = task_log_path(task_id)
    if not path.exists():
        return _err('task log not found')
    content = path.read_text().splitlines()[-lines:]
    return _ok({'task_id': task_id, 'lines': content})


def _dispatch(method: str, params: Dict[str, Any]) -> Dict[str, Any]:
    if method == 'enqueue_goal_task':
        return _ok(create_task('goal', params, requested_by=params.get('_user', 'unknown')))
    if method == 'enqueue_intent_task':
        return _ok(create_task('intent', params, requested_by=params.get('_user', 'unknown')))
    if method == 'get_task_status':
        task = find_task(str(params.get('task_id') or ''))
        return _ok(task) if task else _err('task not found')
    if method == 'list_recent_tasks':
        return _ok(list_tasks(limit=int(params.get('limit', 20)), status=params.get('status')))
    if method == 'tail_task_log':
        return _tail_log(str(params.get('task_id') or ''), int(params.get('lines', 120)))
    if method == 'cancel_background_task':
        result = cancel_task(str(params.get('task_id') or ''))
        return _ok(result) if result.get('ok') else _err(result.get('message', 'cancel failed'))
    if method == 'retry_background_task':
        result = retry_task(str(params.get('task_id') or ''), requested_by=params.get('_user', 'unknown'))
        return _ok(result) if result.get('ok') else _err(result.get('message', 'retry failed'))
    if method == 'get_orchestrator_status':
        return _ok(get_worker_status())
    if method == 'pause_orchestrator':
        return _ok(set_queue_paused(True, reason=params.get('reason') or 'paused by broker client'))
    if method == 'resume_orchestrator':
        return _ok(set_queue_paused(False))
    return _err(f'unknown broker method: {method}')


async def _handle(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
    try:
        raw = await reader.readline()
        if not raw:
            return
        req = json.loads(raw.decode())
        method = str(req.get('method') or '')
        params = req.get('params') or {}
        if not isinstance(params, dict):
            params = {}
        resp = _dispatch(method, params)
    except Exception as exc:
        resp = _err(str(exc))
    writer.write((json.dumps(resp, ensure_ascii=False) + '\n').encode())
    await writer.drain()
    writer.close()
    try:
        await writer.wait_closed()
    except Exception:
        pass


async def main() -> None:
    if BROKER_SOCK.exists():
        BROKER_SOCK.unlink()
    server = await asyncio.start_unix_server(_handle, path=str(BROKER_SOCK))
    os.chmod(BROKER_SOCK, 0o660)
    async with server:
        await server.serve_forever()


if __name__ == '__main__':
    asyncio.run(main())

