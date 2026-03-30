"""Read-only tool cache inspection and control tools."""
from dataclasses import dataclass
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


def register_cache_tools(toolset) -> None:
    async def get_tool_cache_stats(args: Dict[str, Any]) -> Dict[str, Any]:
        text = toolset._get_read_cache_stats_text()
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def clear_tool_cache(args: Dict[str, Any]) -> Dict[str, Any]:
        name = args.get("tool_name")
        removed = toolset._clear_read_cache(tool_name=name)
        text = f"cleared {removed} cache entr{'y' if removed == 1 else 'ies'}" + (f" for {name}" if name else "")
        return {"content": [{"type": "text", "text": text}], "isError": False}

    extra = [
        ExtraToolDefinition("get_tool_cache_stats", "Return in-memory cache stats for read-only tool calls, including entries, hits, misses, and top cached tools.", {"type": "object", "properties": {}, "required": []}, get_tool_cache_stats, False, _ro("Get Tool Cache Stats")),
        ExtraToolDefinition("clear_tool_cache", "Clear the in-memory cache for read-only tool calls, optionally only for one tool name.", {"type": "object", "properties": {"tool_name": {"type": "string"}}, "required": []}, clear_tool_cache, False, _rw("Clear Tool Cache", False)),
    ]

    for tool in extra:
        toolset._register_tool(tool)

