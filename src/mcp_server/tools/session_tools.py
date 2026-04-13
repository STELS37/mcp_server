"""Session tools for sticky workspace context and fast reuse."""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

SESSION_STATE_PATH = Path("/a0/usr/projects/mcp_server/.runtime/session_state.json")


@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


def _ro(title: str) -> Dict[str, Any]:
    return {
        "title": title,
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


def _rw(title: str, destructive: bool = False) -> Dict[str, Any]:
    return {
        "title": title,
        "readOnlyHint": False,
        "destructiveHint": destructive,
        "idempotentHint": False,
        "openWorldHint": False,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


# Project defaults for this server
PROJECT_DEFAULTS = {
    "workspace": "/a0/usr/projects/mcp_server",
    "service": "mcp-server",
    "repo": "mcp_server"
}

def _default_state() -> Dict[str, Any]:
    return {
        **PROJECT_DEFAULTS,
        "last_opened_at": None,
        "history": [],
    }

def _ensure_state() -> None:
    """Ensure session state file exists with defaults if missing."""
    if not SESSION_STATE_PATH.exists():
        _save_state(_default_state())


def _load_state() -> Dict[str, Any]:
    if not SESSION_STATE_PATH.exists():
        return _default_state()
    try:
        data = json.loads(SESSION_STATE_PATH.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data.setdefault("workspace", None)
            data.setdefault("service", None)
            data.setdefault("repo", None)
            data.setdefault("last_opened_at", None)
            data.setdefault("history", [])
            return data
    except Exception:
        pass
    return _default_state()


def _save_state(state: Dict[str, Any]) -> None:
    SESSION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    SESSION_STATE_PATH.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


def _record_event(state: Dict[str, Any], action: str, payload: Dict[str, Any]) -> None:
    history = list(state.get("history") or [])
    history.append({"action": action, "payload": payload, "at": _utc_now()})
    state["history"] = history[-40:]


def _workspace_fingerprint(state: Dict[str, Any]) -> str:
    payload = {
        "workspace": state.get("workspace"),
        "service": state.get("service"),
        "repo": state.get("repo"),
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]


def register_session_tools(toolset) -> None:
    async def open_workspace(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        workspace = args.get("project_root") or args.get("workspace") or "/a0/usr/projects/mcp_server"
        service = args.get("service_name") or state.get("service") or "mcp-server"
        repo = args.get("repo_name") or state.get("repo") or "mcp_server"

        state["workspace"] = workspace
        state["service"] = service
        state["repo"] = repo
        state["last_opened_at"] = _utc_now()

        _record_event(
            state,
            "open_workspace",
            {"workspace": workspace, "service": service, "repo": repo},
        )
        _save_state(state)

        text = (
            f"workspace={workspace}\n"
            f"service={service}\n"
            f"repo={repo}\n"
            f"fingerprint={_workspace_fingerprint(state)}\n"
            f"opened_at={state['last_opened_at']}"
        )
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def get_current_workspace(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        text = json.dumps(
            {
                "workspace": state.get("workspace"),
                "service": state.get("service"),
                "repo": state.get("repo"),
                "last_opened_at": state.get("last_opened_at"),
                "fingerprint": _workspace_fingerprint(state),
            },
            indent=2,
            ensure_ascii=False,
        )
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def set_primary_service(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        service = args.get("service")
        state["service"] = service
        _record_event(state, "set_primary_service", {"service": service})
        _save_state(state)
        return {"content": [{"type": "text", "text": f"service={service}"}], "isError": False}

    async def set_primary_repo(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        repo = args.get("repo")
        state["repo"] = repo
        _record_event(state, "set_primary_repo", {"repo": repo})
        _save_state(state)
        return {"content": [{"type": "text", "text": f"repo={repo}"}], "isError": False}

    async def get_session_state(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _load_state()
        enriched = dict(state)
        enriched["fingerprint"] = _workspace_fingerprint(state)
        return {
            "content": [{"type": "text", "text": json.dumps(enriched, indent=2, ensure_ascii=False)}],
            "isError": False,
        }

    # Auto-initialize session state with project defaults if file is missing
    _ensure_state()

    async def clear_session_state(args: Dict[str, Any]) -> Dict[str, Any]:
        state = _default_state()
        _save_state(state)
        return {"content": [{"type": "text", "text": "session state cleared"}], "isError": False}

    extra = [
        ExtraToolDefinition(
            "open_workspace",
            "Set sticky workspace/service/repo context for this server-side session.",
            {
                "type": "object",
                "properties": {
                    "project_root": {"type": "string"},
                    "workspace": {"type": "string"},
                    "service_name": {"type": "string"},
                    "repo_name": {"type": "string"},
                },
                "additionalProperties": False,
            },
            open_workspace,
            dangerous=False,
            annotations=_rw("Open Workspace", destructive=False),
        ),
        ExtraToolDefinition(
            "get_current_workspace",
            "Return current sticky workspace/service/repo context.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            get_current_workspace,
            dangerous=False,
            annotations=_ro("Get Current Workspace"),
        ),
        ExtraToolDefinition(
            "set_primary_service",
            "Update sticky primary service name.",
            {
                "type": "object",
                "properties": {"service": {"type": "string"}},
                "required": ["service"],
                "additionalProperties": False,
            },
            set_primary_service,
            dangerous=False,
            annotations=_rw("Set Primary Service", destructive=False),
        ),
        ExtraToolDefinition(
            "set_primary_repo",
            "Update sticky primary repository name.",
            {
                "type": "object",
                "properties": {"repo": {"type": "string"}},
                "required": ["repo"],
                "additionalProperties": False,
            },
            set_primary_repo,
            dangerous=False,
            annotations=_rw("Set Primary Repo", destructive=False),
        ),
        ExtraToolDefinition(
            "get_session_state",
            "Return full sticky session state including recent history and fingerprint.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            get_session_state,
            dangerous=False,
            annotations=_ro("Get Session State"),
        ),
        ExtraToolDefinition(
            "clear_session_state",
            "Reset sticky session state to defaults.",
            {"type": "object", "properties": {}, "additionalProperties": False},
            clear_session_state,
            dangerous=False,
            annotations=_rw("Clear Session State", destructive=True),
        ),
    ]

    for t in extra:
        toolset.extra_tools[t.name] = {
            "description": t.description,
            "input_schema": t.input_schema,
            "handler": t.handler,
            "dangerous": t.dangerous,
            "annotations": t.annotations,
        }
