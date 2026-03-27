"""Additional ops tools for mutation and service management."""
import json
import shlex
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


def _rw(title: str, destructive: bool = True) -> Dict[str, Any]:
    return {
        "title": title,
        "readOnlyHint": False,
        "destructiveHint": destructive,
        "idempotentHint": False,
        "openWorldHint": False,
    }


def _ro(title: str) -> Dict[str, Any]:
    return {
        "title": title,
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    }


def register_ops_tools(toolset) -> None:
    async def mkdir_p(args: Dict[str, Any]) -> Dict[str, Any]:
        path = shlex.quote(args.get("path"))
        use_sudo = bool(args.get("use_sudo", False))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"mkdir -p {path}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"created {args.get('path')}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def copy_path(args: Dict[str, Any]) -> Dict[str, Any]:
        src = shlex.quote(args.get("src"))
        dst = shlex.quote(args.get("dst"))
        use_sudo = bool(args.get("use_sudo", False))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"cp -a {src} {dst}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"copied {args.get('src')} -> {args.get('dst')}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def move_path(args: Dict[str, Any]) -> Dict[str, Any]:
        src = shlex.quote(args.get("src"))
        dst = shlex.quote(args.get("dst"))
        use_sudo = bool(args.get("use_sudo", False))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"mv {src} {dst}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"moved {args.get('src')} -> {args.get('dst')}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def remove_path(args: Dict[str, Any]) -> Dict[str, Any]:
        path = shlex.quote(args.get("path"))
        recursive = bool(args.get("recursive", False))
        force = bool(args.get("force", True))
        use_sudo = bool(args.get("use_sudo", False))
        user = args.get("_user", "unknown")
        flags = []
        if recursive:
            flags.append("-r")
        if force:
            flags.append("-f")
        result = await toolset.ssh.execute(f"rm {' '.join(flags)} {path}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"removed {args.get('path')}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def chmod_path(args: Dict[str, Any]) -> Dict[str, Any]:
        path = shlex.quote(args.get("path"))
        mode = shlex.quote(str(args.get("mode")))
        use_sudo = bool(args.get("use_sudo", False))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"chmod {mode} {path}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"chmod {args.get('mode')} {args.get('path')}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def chown_path(args: Dict[str, Any]) -> Dict[str, Any]:
        path = shlex.quote(args.get("path"))
        owner = shlex.quote(str(args.get("owner")))
        recursive = bool(args.get("recursive", False))
        use_sudo = bool(args.get("use_sudo", True))
        user = args.get("_user", "unknown")
        rflag = "-R " if recursive else ""
        result = await toolset.ssh.execute(f"chown {rflag}{owner} {path}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"chown {args.get('owner')} {args.get('path')}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def append_file(args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        content = args.get("content", "")
        use_sudo = bool(args.get("use_sudo", False))
        user = args.get("_user", "unknown")
        qpath = shlex.quote(path)
        qcontent = shlex.quote(content)
        result = await toolset.ssh.execute(f"printf %s {qcontent} >> {qpath}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"appended to {path}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def backup_file(args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        suffix = args.get("suffix") or "bak"
        use_sudo = bool(args.get("use_sudo", False))
        user = args.get("_user", "unknown")
        src = shlex.quote(path)
        dst_path = path + "." + suffix
        dst = shlex.quote(dst_path)
        result = await toolset.ssh.execute(f"cp -a {src} {dst}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": dst_path if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def replace_in_file(args: Dict[str, Any]) -> Dict[str, Any]:
        path = args.get("path")
        search = args.get("search")
        replace = args.get("replace")
        use_sudo = bool(args.get("use_sudo", False))
        user = args.get("_user", "unknown")
        code = (
            "from pathlib import Path; "
            f"p=Path({json.dumps(path)}); "
            f"s={json.dumps(search)}; r={json.dumps(replace)}; "
            "t=p.read_text(); c=t.count(s); p.write_text(t.replace(s,r)); print(c)"
        )
        result = await toolset.ssh.execute("python3 -c " + shlex.quote(code), user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"replacements: {result.stdout.strip()}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def service_unit_exists(args: Dict[str, Any]) -> Dict[str, Any]:
        service = shlex.quote(args.get("service"))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"systemctl status {service} >/dev/null 2>&1; echo $?", user=user)
        code = result.stdout.strip()
        text = "exists" if code in {"0", "3"} else "missing"
        return {"content": [{"type": "text", "text": text}], "isError": False}

    async def service_start(args: Dict[str, Any]) -> Dict[str, Any]:
        service = shlex.quote(args.get("service"))
        use_sudo = bool(args.get("use_sudo", True))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"systemctl start {service}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"started {args.get('service')}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def service_stop(args: Dict[str, Any]) -> Dict[str, Any]:
        service = shlex.quote(args.get("service"))
        use_sudo = bool(args.get("use_sudo", True))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"systemctl stop {service}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"stopped {args.get('service')}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def service_reload(args: Dict[str, Any]) -> Dict[str, Any]:
        service = shlex.quote(args.get("service"))
        use_sudo = bool(args.get("use_sudo", True))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"systemctl reload {service}", user=user, use_sudo=use_sudo)
        return {"content": [{"type": "text", "text": f"reloaded {args.get('service')}" if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def service_restart_and_wait(args: Dict[str, Any]) -> Dict[str, Any]:
        service = shlex.quote(args.get("service"))
        wait_seconds = int(args.get("wait_seconds", 10))
        use_sudo = bool(args.get("use_sudo", True))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"systemctl restart {service} && sleep {wait_seconds} && systemctl is-active {service}", user=user, use_sudo=use_sudo, timeout=wait_seconds + 20)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def journal_grep(args: Dict[str, Any]) -> Dict[str, Any]:
        service = shlex.quote(args.get("service"))
        pattern = shlex.quote(args.get("pattern"))
        lines = int(args.get("lines", 300))
        user = args.get("_user", "unknown")
        cmd = f"journalctl -u {service} -n {lines} --no-pager | grep -n -- {pattern} || true"
        result = await toolset.ssh.execute(cmd, user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or 'no matches'}], "isError": False}

    async def docker_inspect(args: Dict[str, Any]) -> Dict[str, Any]:
        container = shlex.quote(args.get("container"))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"docker inspect {container}", user=user, timeout=int(args.get("timeout", 30)))
        return {"content": [{"type": "text", "text": result.stdout if result.exit_code == 0 else result.stderr}], "isError": result.exit_code != 0}

    async def docker_restart(args: Dict[str, Any]) -> Dict[str, Any]:
        container = shlex.quote(args.get("container"))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"docker restart {container}", user=user, timeout=int(args.get("timeout", 60)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def top_processes(args: Dict[str, Any]) -> Dict[str, Any]:
        sort_by = args.get("sort_by", "cpu")
        limit = int(args.get("limit", 20))
        user = args.get("_user", "unknown")
        sort_flag = "-%cpu" if sort_by == "cpu" else "-%mem"
        result = await toolset.ssh.execute(f"ps aux --sort={sort_flag} | head -n {limit + 1}", user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def pid_exists(args: Dict[str, Any]) -> Dict[str, Any]:
        pid = int(args.get("pid"))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"kill -0 {pid} >/dev/null 2>&1; echo $?", user=user)
        return {"content": [{"type": "text", "text": 'exists' if result.stdout.strip() == '0' else 'missing'}], "isError": False}

    async def process_details(args: Dict[str, Any]) -> Dict[str, Any]:
        pid = int(args.get("pid"))
        user = args.get("_user", "unknown")
        result = await toolset.ssh.execute(f"ps -fp {pid} && echo '\nCMDLINE:' && tr '\0' ' ' </proc/{pid}/cmdline || true", user=user)
        return {"content": [{"type": "text", "text": result.stdout.strip() or 'missing'}], "isError": False}

    extra = [
        ExtraToolDefinition("mkdir_p", "Create a directory path on the VPS, including parents.", {"type": "object", "properties": {"path": {"type": "string", "description": "Directory path to create"}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": False}}, "required": ["path"]}, mkdir_p, True, _rw("Mkdir P", False)),
        ExtraToolDefinition("copy_path", "Copy a file or directory on the VPS.", {"type": "object", "properties": {"src": {"type": "string", "description": "Source path"}, "dst": {"type": "string", "description": "Destination path"}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": False}}, "required": ["src", "dst"]}, copy_path, True, _rw("Copy Path")),
        ExtraToolDefinition("move_path", "Move or rename a file or directory on the VPS.", {"type": "object", "properties": {"src": {"type": "string", "description": "Source path"}, "dst": {"type": "string", "description": "Destination path"}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": False}}, "required": ["src", "dst"]}, move_path, True, _rw("Move Path")),
        ExtraToolDefinition("remove_path", "Remove a file or directory on the VPS.", {"type": "object", "properties": {"path": {"type": "string", "description": "Path to remove"}, "recursive": {"type": "boolean", "description": "Recursive removal", "default": False}, "force": {"type": "boolean", "description": "Force removal", "default": True}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": False}}, "required": ["path"]}, remove_path, True, _rw("Remove Path")),
        ExtraToolDefinition("chmod_path", "Change file mode on the VPS.", {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}, "mode": {"type": "string", "description": "Mode, e.g. 644 or 755"}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": False}}, "required": ["path", "mode"]}, chmod_path, True, _rw("Chmod Path")),
        ExtraToolDefinition("chown_path", "Change file owner/group on the VPS.", {"type": "object", "properties": {"path": {"type": "string", "description": "Path"}, "owner": {"type": "string", "description": "owner or owner:group"}, "recursive": {"type": "boolean", "description": "Recursive", "default": False}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": True}}, "required": ["path", "owner"]}, chown_path, True, _rw("Chown Path")),
        ExtraToolDefinition("append_file", "Append text to a file on the VPS.", {"type": "object", "properties": {"path": {"type": "string", "description": "File path"}, "content": {"type": "string", "description": "Text to append"}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": False}}, "required": ["path", "content"]}, append_file, True, _rw("Append File", False)),
        ExtraToolDefinition("backup_file", "Create a backup copy of a file on the VPS.", {"type": "object", "properties": {"path": {"type": "string", "description": "File path to back up"}, "suffix": {"type": "string", "description": "Optional backup suffix"}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": False}}, "required": ["path"]}, backup_file, True, _rw("Backup File", False)),
        ExtraToolDefinition("replace_in_file", "Replace text in a file on the VPS.", {"type": "object", "properties": {"path": {"type": "string", "description": "File path"}, "search": {"type": "string", "description": "Text to search for"}, "replace": {"type": "string", "description": "Replacement text"}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": False}}, "required": ["path", "search", "replace"]}, replace_in_file, True, _rw("Replace In File", False)),
        ExtraToolDefinition("service_unit_exists", "Check whether a systemd unit exists.", {"type": "object", "properties": {"service": {"type": "string", "description": "Service name"}}, "required": ["service"]}, service_unit_exists, False, _ro("Service Unit Exists")),
        ExtraToolDefinition("service_start", "Start a systemd service.", {"type": "object", "properties": {"service": {"type": "string", "description": "Service name"}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": True}}, "required": ["service"]}, service_start, True, _rw("Service Start")),
        ExtraToolDefinition("service_stop", "Stop a systemd service.", {"type": "object", "properties": {"service": {"type": "string", "description": "Service name"}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": True}}, "required": ["service"]}, service_stop, True, _rw("Service Stop")),
        ExtraToolDefinition("service_reload", "Reload a systemd service.", {"type": "object", "properties": {"service": {"type": "string", "description": "Service name"}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": True}}, "required": ["service"]}, service_reload, True, _rw("Service Reload")),
        ExtraToolDefinition("service_restart_and_wait", "Restart a systemd service and wait for active state.", {"type": "object", "properties": {"service": {"type": "string", "description": "Service name"}, "wait_seconds": {"type": "integer", "description": "Seconds to wait after restart", "default": 10}, "use_sudo": {"type": "boolean", "description": "Use sudo", "default": True}}, "required": ["service"]}, service_restart_and_wait, True, _rw("Service Restart And Wait")),
        ExtraToolDefinition("journal_grep", "Search recent journal logs for a service by pattern.", {"type": "object", "properties": {"service": {"type": "string", "description": "Service name"}, "pattern": {"type": "string", "description": "Text or regex to match"}, "lines": {"type": "integer", "description": "Recent lines to scan", "default": 300}}, "required": ["service", "pattern"]}, journal_grep, False, _ro("Journal Grep")),
        ExtraToolDefinition("docker_inspect", "Inspect a Docker container and return the raw JSON.", {"type": "object", "properties": {"container": {"type": "string", "description": "Container name or ID"}, "timeout": {"type": "integer", "description": "Command timeout", "default": 30}}, "required": ["container"]}, docker_inspect, False, _ro("Docker Inspect")),
        ExtraToolDefinition("docker_restart", "Restart a Docker container.", {"type": "object", "properties": {"container": {"type": "string", "description": "Container name or ID"}, "timeout": {"type": "integer", "description": "Restart timeout", "default": 60}}, "required": ["container"]}, docker_restart, True, _rw("Docker Restart")),
        ExtraToolDefinition("top_processes", "Show top processes by CPU or memory.", {"type": "object", "properties": {"sort_by": {"type": "string", "description": "cpu or mem", "default": "cpu"}, "limit": {"type": "integer", "description": "Number of rows", "default": 20}}, "required": []}, top_processes, False, _ro("Top Processes")),
        ExtraToolDefinition("pid_exists", "Check whether a PID exists.", {"type": "object", "properties": {"pid": {"type": "integer", "description": "Process ID"}}, "required": ["pid"]}, pid_exists, False, _ro("Pid Exists")),
        ExtraToolDefinition("process_details", "Read details and cmdline for a PID.", {"type": "object", "properties": {"pid": {"type": "integer", "description": "Process ID"}}, "required": ["pid"]}, process_details, False, _ro("Process Details")),
    ]

    for tool in extra:
        toolset._register_tool(tool)

