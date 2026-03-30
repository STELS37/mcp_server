"""State and ledger tools for action history, failures, and edit traces."""
import json
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

STATE_PATH = Path("/a0/usr/projects/mcp_server/.runtime/agent_state.json")


@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


def _ro(title: str) -> Dict[str, Any]:
    return {"title": title, "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


def _rw(title: str, destructive: bool = False) -> Dict[str, Any]:
    return {"title": title, "readOnlyHint": False, "destructiveHint": destructive, "idempotentHint": False, "openWorldHint": False}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _default_state() -> Dict[str, Any]:
    return {"actions": [], "health_snapshots": [], "edits": []}


def _load_state() -> Dict[str, Any]:
    if not STATE_PATH.exists():
        return _default_state()
    try:
        data = json.loads(STATE_PATH.read_text())
        if isinstance(data, dict):
            data.setdefault("actions", [])
            data.setdefault("health_snapshots", [])
            data.setdefault("edits", [])
            return data
    except Exception:
        pass
    return _default_state()


def _save_state(state: Dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False))


def _append_bounded(state: Dict[str, Any], key: str, item: Dict[str, Any], limit: int = 200) -> None:
    arr = list(state.get(key) or [])
    arr.append(item)
    state[key] = arr[-limit:]


def _parse_ts(value: Optional[str]):
    if not value:
        return None
    try:
        if value.endswith('Z'):
            value = value[:-1] + '+00:00'
        return datetime.fromisoformat(value)
    except Exception:
        return None


def _match_item(item: Dict[str, Any], args: Dict[str, Any]) -> bool:
    target_contains = str(args.get("target_contains") or "").strip().lower()
    action_name = str(args.get("action_name") or "").strip().lower()
    fingerprint = str(args.get("call_fingerprint") or "").strip().lower()
    since_minutes = args.get("since_minutes")
    status = str(args.get("status") or "").strip().lower()
    if target_contains and target_contains not in str(item.get("target") or "").lower():
        return False
    if action_name and action_name not in str(item.get("action_name") or "").lower():
        return False
    if fingerprint and fingerprint != str(item.get("call_fingerprint") or "").lower():
        return False
    if status and status != str(item.get("status") or "").lower():
        return False
    if since_minutes is not None:
        ts = _parse_ts(item.get("at"))
        if ts is None:
            return False
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=int(since_minutes))
        if ts < cutoff:
            return False
    return True


def register_state_tools(toolset) -> None:
    async def record_action_result(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        item = {"action_name": args.get("action_name"), "status": args.get("status"), "target": args.get("target"), "details": args.get("details"), "at": _utc_now()}
        _append_bounded(state, "actions", item)
        if args.get("category") == "edit":
            _append_bounded(state, "edits", item)
        if args.get("category") == "health":
            _append_bounded(state, "health_snapshots", item)
        _save_state(state)
        return {"content": [{"type": "text", "text": "recorded"}], "isError": False}

    async def get_recent_failures(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        limit = int(args.get("limit", 20))
        rows = [x for x in state.get("actions", []) if str(x.get("status", "")).lower() not in {"ok", "success", "passed"}]
        rows = [x for x in rows if _match_item(x, args)]
        return {"content": [{"type": "text", "text": json.dumps(rows[-limit:], indent=2, ensure_ascii=False)}], "isError": False}

    async def get_recent_edits(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        limit = int(args.get("limit", 20))
        rows = [x for x in state.get("edits", []) if _match_item(x, args)]
        return {"content": [{"type": "text", "text": json.dumps(rows[-limit:], indent=2, ensure_ascii=False)}], "isError": False}

    async def get_last_service_actions(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        service = args.get("service")
        limit = int(args.get("limit", 20))
        rows = []
        for item in state.get("actions", []):
            target = str(item.get("target") or "")
            name = str(item.get("action_name") or "")
            if (not service or service in target) and ("service" in name or "systemd" in name or service in target):
                if _match_item(item, args):
                    rows.append(item)
        return {"content": [{"type": "text", "text": json.dumps(rows[-limit:], indent=2, ensure_ascii=False)}], "isError": False}

    async def get_last_health_snapshot(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        rows = [x for x in (state.get("health_snapshots") or []) if _match_item(x, args)]
        last = rows[-1:] or []
        text = json.dumps(last[0] if last else {}, indent=2, ensure_ascii=False)
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def cleanup_action_ledger(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        keep_last = int(args.get("keep_last", 200))
        drop_older_than_minutes = args.get("drop_older_than_minutes")
        cleaned = {}
        removed = {}
        for key in ("actions", "health_snapshots", "edits"):
            rows = list(state.get(key) or [])
            original = len(rows)
            if drop_older_than_minutes is not None:
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=int(drop_older_than_minutes))
                tmp = []
                for item in rows:
                    ts = _parse_ts(item.get("at"))
                    if ts is None or ts >= cutoff:
                        tmp.append(item)
                rows = tmp
            rows = rows[-keep_last:]
            cleaned[key] = rows
            removed[key] = original - len(rows)
        _save_state(cleaned)
        payload = {"removed": removed, "remaining": {k: len(v) for k, v in cleaned.items()}}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    extra = [
        ExtraToolDefinition("record_action_result", "Persist an action result into the agent state ledger for later anti-loop diagnostics.", {"type": "object", "properties": {"action_name": {"type": "string"}, "status": {"type": "string"}, "target": {"type": "string"}, "details": {"type": "string"}, "category": {"type": "string", "description": "general, edit, or health"}}, "required": ["action_name", "status"]}, record_action_result, False, _rw("Record Action Result", False)),
        ExtraToolDefinition("get_recent_failures", "Return failed or degraded actions from the server-side state ledger, with optional filters by time, target, action, status, or call fingerprint.", {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}, "since_minutes": {"type": "integer"}, "target_contains": {"type": "string"}, "action_name": {"type": "string"}, "status": {"type": "string"}, "call_fingerprint": {"type": "string"}}, "required": []}, get_recent_failures, False, _ro("Get Recent Failures")),
        ExtraToolDefinition("get_recent_edits", "Return recorded edit operations from the server-side state ledger, with optional filters by time, target, action, status, or call fingerprint.", {"type": "object", "properties": {"limit": {"type": "integer", "default": 20}, "since_minutes": {"type": "integer"}, "target_contains": {"type": "string"}, "action_name": {"type": "string"}, "status": {"type": "string"}, "call_fingerprint": {"type": "string"}}, "required": []}, get_recent_edits, False, _ro("Get Recent Edits")),
        ExtraToolDefinition("get_last_service_actions", "Return service-related actions for a service or for all services, with optional filters by time, action, status, or call fingerprint.", {"type": "object", "properties": {"service": {"type": "string"}, "limit": {"type": "integer", "default": 20}, "since_minutes": {"type": "integer"}, "action_name": {"type": "string"}, "status": {"type": "string"}, "call_fingerprint": {"type": "string"}}, "required": []}, get_last_service_actions, False, _ro("Get Last Service Actions")),
        ExtraToolDefinition("get_last_health_snapshot", "Return the last recorded health snapshot from the state ledger, optionally filtered by time, target, action, or call fingerprint.", {"type": "object", "properties": {"since_minutes": {"type": "integer"}, "target_contains": {"type": "string"}, "action_name": {"type": "string"}, "call_fingerprint": {"type": "string"}}, "required": []}, get_last_health_snapshot, False, _ro("Get Last Health Snapshot")),
        ExtraToolDefinition("cleanup_action_ledger", "Trim old noise from the action ledger by keeping only the newest entries and optionally dropping entries older than a time window.", {"type": "object", "properties": {"keep_last": {"type": "integer", "default": 200}, "drop_older_than_minutes": {"type": "integer"}}, "required": []}, cleanup_action_ledger, False, _rw("Cleanup Action Ledger", False)),
    ]

    for tool in extra:
        toolset._register_tool(tool)

