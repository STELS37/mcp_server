"""Extra narrow MCP tools for high-autonomy diagnostics, file inspection, and service bundles."""
import json
import shlex
import time
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
    return {
        "title": title,
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


def register_extra_tools(toolset) -> None:
    """Register additional narrow tools on an MCPTools instance."""

    async def exists_path(args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        user = args.get("_user", "unknown")
        q = shlex.quote(path)
        cmd = (
            f"if [ -e {q} ]; then "
            f"if [ -d {q} ]; then echo 'exists: directory'; "
            f"elif [ -f {q} ]; then echo 'exists: file'; "
            f"else echo 'exists: other'; fi; "
            f"else echo 'missing'; fi"
        )
        result = await toolset.ssh.execute(cmd, user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def stat_path(args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        user = args.get("_user", "unknown")
        q = shlex.quote(path)
        cmd = "stat -c " + shlex.quote("PATH=%n\nTYPE=%F\nSIZE=%s\nMODE=%a\nOWNER=%U\nGROUP=%G\nMTIME=%y\nATIME=%x\nCTIME=%z") + f" {q}"
        result = await toolset.ssh.execute(cmd, user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def tail_file(args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        lines = int(args.get("lines", 100))
        user = args.get("_user", "unknown")
        q = shlex.quote(path)
        result = await toolset.ssh.execute(f"tail -n {lines} {q}", user=user)
        return {"content": [{"type": "text", "text": result.stdout if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def grep_file(args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        pattern = args.get("pattern")
        ignore_case = bool(args.get("ignore_case", False))
        max_matches = int(args.get("max_matches", 200))
        user = args.get("_user", "unknown")
        qpath = shlex.quote(path)
        qpat = shlex.quote(pattern)
        flags = "-ni" if ignore_case else "-n"
        cmd = f"grep {flags} -m {max_matches} -- {qpat} {qpath} || true"
        result = await toolset.ssh.execute(cmd, user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or 'no matches'}], "isError": False}

    async def port_check_local(args: Dict[str, Any]) -> Dict[str, Any]:
        host = args.get("host", "127.0.0.1")
        port = int(args.get("port"))
        timeout = float(args.get("timeout", 3))
        user = args.get("_user", "unknown")
        code = (
            "import socket, json; "
            f"host={json.dumps(host)}; port={port}; timeout={timeout}; "
            "s=socket.socket(); s.settimeout(timeout); "
            "rc=s.connect_ex((host, port)); "
            "print(json.dumps({'open': rc==0, 'code': rc})); s.close()"
        )
        result = await toolset.ssh.execute("python3 -c " + shlex.quote(code), user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def process_check(args: Dict[str, Any]) -> Dict[str, Any]:
        pattern = args.get("pattern")
        max_lines = int(args.get("max_lines", 50))
        user = args.get("_user", "unknown")
        qpat = shlex.quote(pattern)
        cmd = f"ps aux | grep -i -- {qpat} | grep -v grep | head -n {max_lines} || true"
        result = await toolset.ssh.execute(cmd, user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or 'no matching processes'}], "isError": False}

    async def list_listeners(args: Dict[str, Any]) -> Dict[str, Any]:
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute("ss -ltnp", user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def find_files(args: Dict[str, Any]) -> Dict[str, Any]:
        root = shlex.quote(args.get("root", "/"))
        name = args.get("name")
        max_results = int(args.get("max_results", 200))
        timeout = int(args.get("timeout", 30))
        user = args.get("_user", "unknown")
        parts = [f"find {root}"]
        if name:
            parts.append(f"-iname {shlex.quote(name)}")
        parts.append(f"2>/dev/null | head -n {max_results}")
        result = await toolset.ssh.execute(" ".join(parts), user=user, timeout=timeout)
        return {"content": [{"type": "text", "text": result.stdout.strip() or 'no matches'}], "isError": result.exit_code != 0}

    async def list_tree(args: Dict[str, Any]) -> Dict[str, Any]:
        root = shlex.quote(args.get("root", "."))
        depth = int(args.get("depth", 3))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"find {root} -maxdepth {depth} | sed -n '1,400p'", user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def du_path(args: Dict[str, Any]) -> Dict[str, Any]:
        path = shlex.quote(args.get("path"))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"du -sh {path}", user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def read_json_file(args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        user = args.get("_user", "unknown")
        code = "import json; data=json.load(open(" + json.dumps(path) + ")); print(json.dumps(data, indent=2, ensure_ascii=False))"
        result = await toolset.ssh.execute("python3 -c " + shlex.quote(code), user=user)
        return {"content": [{"type": "text", "text": result.stdout if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def read_env_file(args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        user = args.get("_user", "unknown")
        code = (
            "import json; from pathlib import Path; out={}; p=Path(" + json.dumps(path) + "); "
            "lines=p.read_text().splitlines(); "
            "[out.setdefault(line.split('=',1)[0].strip(), line.split('=',1)[1].strip()) for line in lines if line.strip() and not line.strip().startswith('#') and '=' in line]; "
            "print(json.dumps(out, indent=2, ensure_ascii=False))"
        )
        result = await toolset.ssh.execute("python3 -c " + shlex.quote(code), user=user)
        return {"content": [{"type": "text", "text": result.stdout if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def service_health_bundle(args: Dict[str, Any]) -> Dict[str, Any]:
        service = args.get("service")
        port = args.get("port")
        health_path = args.get("health_path", "/health")
        timeout = int(args.get("timeout", 30))
        user = args.get("_user", "unknown")
        qservice = shlex.quote(service)
        parts = [f"echo 'SERVICE:'; systemctl is-active {qservice} || true", f"echo '\nSTATUS:'; systemctl status {qservice} --no-pager | sed -n '1,20p' || true"]
        if port:
            parts.append(f"echo '\nPORT:'; ss -ltn '( sport = :{int(port)} )' || true")
        if port and health_path:
            parts.append(f"echo '\nHEALTH:'; curl -fsS http://127.0.0.1:{int(port)}{health_path} || true")
        parts.append(f"echo '\nLOGS:'; journalctl -u {qservice} -n 40 --no-pager || true")
        result = await toolset.ssh.execute("; ".join(parts), user=user, timeout=timeout)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": False}

    async def diagnose_service(args: Dict[str, Any]) -> Dict[str, Any]:
        service = args.get("service")
        port = args.get("port")
        timeout = int(args.get("timeout", 30))
        user = args.get("_user", "unknown")
        qservice = shlex.quote(service)
        parts = [f"echo 'ACTIVE:'; systemctl is-active {qservice} || true", f"echo '\nSTATUS:'; systemctl status {qservice} --no-pager | sed -n '1,30p' || true", f"echo '\nPROCESSES:'; ps aux | grep -i -- {qservice} | grep -v grep | head -n 20 || true"]
        if port:
            parts.append(f"echo '\nPORT:'; ss -ltnp | grep ':{int(port)} ' || true")
        parts.append(f"echo '\nLOGS:'; journalctl -u {qservice} -n 60 --no-pager || true")
        result = await toolset.ssh.execute("; ".join(parts), user=user, timeout=timeout)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": False}

    async def diagnose_port(args: Dict[str, Any]) -> Dict[str, Any]:
        port = int(args.get("port"))
        user = args.get("_user", "unknown")
        cmd = f"echo 'LISTENERS:'; ss -ltnp | grep ':{port} ' || true; echo '\nPROCESSES:'; lsof -i :{port} 2>/dev/null || true"
        result = await toolset.ssh.execute(cmd, user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": False}

    async def mcp_self_test(args: Dict[str, Any]) -> Dict[str, Any]:
        port = int(args.get("port", 8000))
        timeout = int(args.get("timeout", 30))
        user = args.get("_user", "unknown")
        tmp = "/a0/usr/projects/mcp_server/.runtime/mcp_self_test.txt"
        parts = [f"echo 'HEALTH'; curl -fsS http://127.0.0.1:{port}/health || true", f"echo '\nREADY'; curl -fsS http://127.0.0.1:{port}/ready || true", f"echo '\nPORT'; ss -ltn '( sport = :{port} )' || true", f"echo '\nWRITE'; printf test > {shlex.quote(tmp)} && cat {shlex.quote(tmp)} || true", "echo '\nSSH'; whoami && hostname || true"]
        result = await toolset.ssh.execute("; ".join(parts), user=user, timeout=timeout)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": False}

    extra = [
        ExtraToolDefinition("exists_path", "Check whether a path exists on the VPS and whether it is a file or directory.", {"type": "object", "properties": {"path": {"type": "string", "description": "Absolute path to inspect"}}, "required": ["path"]}, exists_path, False, _ro("Exists Path")),
        ExtraToolDefinition("stat_path", "Read file or directory metadata on the VPS.", {"type": "object", "properties": {"path": {"type": "string", "description": "Absolute path to inspect"}}, "required": ["path"]}, stat_path, False, _ro("Stat Path")),
        ExtraToolDefinition("tail_file", "Read the last N lines of a file on the VPS.", {"type": "object", "properties": {"path": {"type": "string", "description": "Absolute file path"}, "lines": {"type": "integer", "description": "Number of lines to return (default: 100)", "default": 100}}, "required": ["path"]}, tail_file, False, _ro("Tail File")),
        ExtraToolDefinition("grep_file", "Search for a text pattern inside a file on the VPS and return matching lines.", {"type": "object", "properties": {"path": {"type": "string", "description": "Absolute file path"}, "pattern": {"type": "string", "description": "Text or regex pattern to search for"}, "ignore_case": {"type": "boolean", "description": "Case-insensitive search", "default": False}, "max_matches": {"type": "integer", "description": "Maximum matching lines to return (default: 200)", "default": 200}}, "required": ["path", "pattern"]}, grep_file, False, _ro("Grep File")),
        ExtraToolDefinition("port_check_local", "Check whether a local TCP port is reachable from the VPS without using a generic shell command.", {"type": "object", "properties": {"port": {"type": "integer", "description": "TCP port to test"}, "host": {"type": "string", "description": "Host to test (default: 127.0.0.1)", "default": "127.0.0.1"}, "timeout": {"type": "number", "description": "Connect timeout in seconds (default: 3)", "default": 3}}, "required": ["port"]}, port_check_local, False, _ro("Port Check Local")),
        ExtraToolDefinition("process_check", "List processes matching a text pattern on the VPS.", {"type": "object", "properties": {"pattern": {"type": "string", "description": "Text to search for in the process list"}, "max_lines": {"type": "integer", "description": "Maximum process lines to return (default: 50)", "default": 50}}, "required": ["pattern"]}, process_check, False, _ro("Process Check")),
        ExtraToolDefinition("list_listeners", "List listening TCP sockets and owning processes on the VPS.", {"type": "object", "properties": {}, "required": []}, list_listeners, False, _ro("List Listeners")),
        ExtraToolDefinition("find_files", "Find files or directories under a root path.", {"type": "object", "properties": {"root": {"type": "string", "description": "Search root", "default": "/"}, "name": {"type": "string", "description": "Case-insensitive filename pattern, e.g. *.log"}, "max_results": {"type": "integer", "description": "Maximum paths to return", "default": 200}, "timeout": {"type": "integer", "description": "Search timeout", "default": 30}}, "required": []}, find_files, False, _ro("Find Files")),
        ExtraToolDefinition("list_tree", "List a filesystem tree up to a max depth.", {"type": "object", "properties": {"root": {"type": "string", "description": "Root path", "default": "."}, "depth": {"type": "integer", "description": "Max depth", "default": 3}}, "required": []}, list_tree, False, _ro("List Tree")),
        ExtraToolDefinition("du_path", "Read summarized disk usage for a path.", {"type": "object", "properties": {"path": {"type": "string", "description": "Path to measure"}}, "required": ["path"]}, du_path, False, _ro("Du Path")),
        ExtraToolDefinition("read_json_file", "Read and pretty-print a JSON file on the VPS.", {"type": "object", "properties": {"path": {"type": "string", "description": "JSON file path"}}, "required": ["path"]}, read_json_file, False, _ro("Read Json File")),
        ExtraToolDefinition("read_env_file", "Read a simple env file as key-value pairs.", {"type": "object", "properties": {"path": {"type": "string", "description": "Env file path"}}, "required": ["path"]}, read_env_file, False, _ro("Read Env File")),
        ExtraToolDefinition("service_health_bundle", "Collect active state, status, optional port, optional health endpoint, and recent logs for a service.", {"type": "object", "properties": {"service": {"type": "string", "description": "Service name"}, "port": {"type": "integer", "description": "Optional local port to inspect"}, "health_path": {"type": "string", "description": "Optional local health path", "default": "/health"}, "timeout": {"type": "integer", "description": "Bundle timeout", "default": 30}}, "required": ["service"]}, service_health_bundle, False, _ro("Service Health Bundle")),
        ExtraToolDefinition("diagnose_service", "Collect status, matching processes, optional port info, and recent logs for a service.", {"type": "object", "properties": {"service": {"type": "string", "description": "Service name"}, "port": {"type": "integer", "description": "Optional port to inspect"}, "timeout": {"type": "integer", "description": "Bundle timeout", "default": 30}}, "required": ["service"]}, diagnose_service, False, _ro("Diagnose Service")),
        ExtraToolDefinition("diagnose_port", "Collect listeners and owning processes for a local port.", {"type": "object", "properties": {"port": {"type": "integer", "description": "Port number"}}, "required": ["port"]}, diagnose_port, False, _ro("Diagnose Port")),
        ExtraToolDefinition("mcp_self_test", "Run a compact MCP self-test bundle including health, ready, port, temp write, and SSH basics.", {"type": "object", "properties": {"port": {"type": "integer", "description": "Local MCP port", "default": 8000}, "timeout": {"type": "integer", "description": "Bundle timeout", "default": 30}}, "required": []}, mcp_self_test, False, _ro("Mcp Self Test")),
    ]

    for tool in extra:
        toolset._register_tool(tool)

