"""Hash-aware safe edit tools with optional rollback support."""
import hashlib
import json
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional


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


def _hash_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _backup_path(path: Path) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return Path(str(path) + f".{ts}.bak")


def register_safe_edit_tools(toolset) -> None:
    async def read_file_with_hash(args: Dict[str, Any]) -> Dict[str, Any]:
        path = Path(args.get("path"))
        max_size = int(args.get("max_size", 262144))
        text = path.read_text()
        if len(text.encode()) > max_size:
            text = text.encode()[:max_size].decode(errors="ignore")
        payload = {"path": str(path), "sha256": _hash_text(text), "content": text}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def replace_in_file_if_hash_matches(args: Dict[str, Any]) -> Dict[str, Any]:
        path = Path(args.get("path"))
        expected_hash = args.get("expected_hash")
        search = args.get("search")
        replace = args.get("replace")
        create_backup = bool(args.get("create_backup", True))
        text = path.read_text()
        actual_hash = _hash_text(text)
        if expected_hash and actual_hash != expected_hash:
            return {"content": [{"type": "text", "text": f"hash mismatch: expected={expected_hash} actual={actual_hash}"}], "isError": True}
        backup = None
        if create_backup:
            backup = _backup_path(path)
            shutil.copy2(path, backup)
        count = text.count(search)
        new_text = text.replace(search, replace)
        path.write_text(new_text)
        payload = {"path": str(path), "replacements": count, "new_hash": _hash_text(new_text), "backup_path": str(backup) if backup else None}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def write_file_if_hash_matches(args: Dict[str, Any]) -> Dict[str, Any]:
        path = Path(args.get("path"))
        expected_hash = args.get("expected_hash")
        content = args.get("content")
        create_backup = bool(args.get("create_backup", True))
        old_text = path.read_text() if path.exists() else ""
        actual_hash = _hash_text(old_text)
        if expected_hash and actual_hash != expected_hash:
            return {"content": [{"type": "text", "text": f"hash mismatch: expected={expected_hash} actual={actual_hash}"}], "isError": True}
        backup = None
        if create_backup and path.exists():
            backup = _backup_path(path)
            shutil.copy2(path, backup)
        path.write_text(content)
        payload = {"path": str(path), "new_hash": _hash_text(content), "backup_path": str(backup) if backup else None}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    async def rollback_file_from_backup(args: Dict[str, Any]) -> Dict[str, Any]:
        path = Path(args.get("path"))
        backup_path = args.get("backup_path")
        if backup_path:
            backup = Path(backup_path)
        else:
            candidates = sorted(path.parent.glob(path.name + ".*.bak"))
            if not candidates:
                return {"content": [{"type": "text", "text": "no backup found"}], "isError": True}
            backup = candidates[-1]
        shutil.copy2(backup, path)
        payload = {"path": str(path), "restored_from": str(backup), "sha256": _hash_text(path.read_text())}
        return {"content": [{"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}], "isError": False}

    extra = [
        ExtraToolDefinition("read_file_with_hash", "Read a file and return both contents and a stable SHA256 hash for safe optimistic edits.", {"type": "object", "properties": {"path": {"type": "string"}, "max_size": {"type": "integer", "default": 262144}}, "required": ["path"]}, read_file_with_hash, False, _ro("Read File With Hash")),
        ExtraToolDefinition("replace_in_file_if_hash_matches", "Replace text in a file only if the current file hash matches the expected hash.", {"type": "object", "properties": {"path": {"type": "string"}, "expected_hash": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "create_backup": {"type": "boolean", "default": True}}, "required": ["path", "expected_hash", "search", "replace"]}, replace_in_file_if_hash_matches, False, _rw("Replace In File If Hash Matches", False)),
        ExtraToolDefinition("write_file_if_hash_matches", "Write a full file only if its current hash still matches the expected hash.", {"type": "object", "properties": {"path": {"type": "string"}, "expected_hash": {"type": "string"}, "content": {"type": "string"}, "create_backup": {"type": "boolean", "default": True}}, "required": ["path", "expected_hash", "content"]}, write_file_if_hash_matches, False, _rw("Write File If Hash Matches", False)),
        ExtraToolDefinition("rollback_file_from_backup", "Restore a file from a provided backup path or the latest timestamped backup.", {"type": "object", "properties": {"path": {"type": "string"}, "backup_path": {"type": "string"}}, "required": ["path"]}, rollback_file_from_backup, False, _rw("Rollback File From Backup", False)),
    ]

    for tool in extra:
        toolset._register_tool(tool)

