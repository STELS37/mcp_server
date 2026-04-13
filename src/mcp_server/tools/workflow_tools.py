"""Higher-level workflow tools to reduce repetitive multi-step troubleshooting."""
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
    return {"title": title, "readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}


def _rw(title: str, destructive: bool = False) -> Dict[str, Any]:
    return {"title": title, "readOnlyHint": False, "destructiveHint": destructive, "idempotentHint": False, "openWorldHint": False}


def _project_root(project: Optional[str], project_root: Optional[str]) -> str:
    if project_root:
        return project_root
    project = project or "mcp_server"
    return project if str(project).startswith('/') else f"/a0/usr/projects/{project}"


def _optional_service_parts(service: Optional[str]) -> list[str]:
    if not service:
        return []
    qservice = shlex.quote(service)
    return [
        f"echo '== RESTART ==' && systemctl restart {qservice} && systemctl is-active {qservice} || true",
        f"echo '== STATUS ==' && systemctl status {qservice} --no-pager | sed -n '1,30p' || true",
        f"echo '== LOGS ==' && journalctl -u {qservice} -n 80 --no-pager || true",
    ]


def _optional_port_parts(port: Optional[int]) -> list[str]:
    if not port:
        return []
    return [
        f"echo '== PORT ==' && ss -ltnp | grep ':{int(port)} ' || true",
        f"echo '== HEALTH ==' && curl -fsS http://127.0.0.1:{int(port)}/health || true",
        f"echo '== READY ==' && curl -fsS http://127.0.0.1:{int(port)}/ready || true",
    ]


def register_workflow_tools(toolset) -> None:
    async def debug_service_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        service = args.get("service")
        port = args.get("port")
        log_path = args.get("log_path")
        timeout = int(args.get("timeout", 40))
        user = args.get("_user", "unknown")
        qservice = shlex.quote(service)
        parts = [
            f"echo 'ACTIVE:'; systemctl is-active {qservice} || true",
            f"echo '\nSTATUS:'; systemctl status {qservice} --no-pager | sed -n '1,30p' || true",
            f"echo '\nLOGS:'; journalctl -u {qservice} -n 60 --no-pager || true",
        ]
        if port:
            parts.append(f"echo '\nPORT:'; ss -ltnp | grep ':{int(port)} ' || true")
            parts.append(f"echo '\nHEALTH:'; curl -fsS http://127.0.0.1:{int(port)}/health || true")
            parts.append(f"echo '\nREADY:'; curl -fsS http://127.0.0.1:{int(port)}/ready || true")
        if log_path:
            parts.append(f"echo '\nTAIL FILE:'; tail -n 80 {shlex.quote(log_path)} || true")
        result = await toolset.ssh.execute('; '.join(parts), user=user, timeout=timeout)
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": False}

    async def safe_edit_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        search = args.get("search")
        replace = args.get("replace")
        restart_service = args.get("restart_service")
        verify_port = args.get("verify_port")
        verify_health = bool(args.get("verify_health", True))
        user = args.get("_user", "unknown")
        code = (
            "from pathlib import Path; import shutil; "
            f"p=Path({json.dumps(args.get('path'))}); "
            "backup=str(p)+'.workflow.bak'; shutil.copy2(p, backup); "
            f"s={json.dumps(search)}; r={json.dumps(replace)}; "
            "t=p.read_text(); c=t.count(s); p.write_text(t.replace(s,r)); print(backup); print(c)"
        )
        parts = [f"echo 'EDIT:'; python3 -c {shlex.quote(code)}"]
        if restart_service:
            qservice = shlex.quote(restart_service)
            parts.append(f"echo '\nRESTART:'; systemctl restart {qservice} && systemctl is-active {qservice} || true")
        if verify_port:
            parts.append(f"echo '\nPORT:'; ss -ltnp | grep ':{int(verify_port)} ' || true")
        if verify_port and verify_health:
            parts.append(f"echo '\nHEALTH:'; curl -fsS http://127.0.0.1:{int(verify_port)}/health || true")
            parts.append(f"echo '\nREADY:'; curl -fsS http://127.0.0.1:{int(verify_port)}/ready || true")
        result = await toolset.ssh.execute('; '.join(parts), user=user, use_sudo=bool(args.get('use_sudo', False)), timeout=int(args.get('timeout', 60)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def collect_project_diagnostics(args: Dict[str, Any]) -> Dict[str, Any]:
        root = shlex.quote(args.get("project_root"))
        service = args.get("service_name")
        port = args.get("port")
        user = args.get("_user", "unknown")
        parts = [f"echo 'TREE:'; find {root} -maxdepth 2 | sed -n '1,120p' || true", f"echo '\nDISK:'; du -sh {root} || true"]
        if service:
            qservice = shlex.quote(service)
            parts.append(f"echo '\nSERVICE:'; systemctl status {qservice} --no-pager | sed -n '1,25p' || true")
        if port:
            parts.append(f"echo '\nPORT:'; ss -ltnp | grep ':{int(port)} ' || true")
        result = await toolset.ssh.execute('; '.join(parts), user=user, timeout=int(args.get('timeout', 40)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": False}

    async def repo_sync_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        project = args.get("project") or args.get("project_root")
        user = args.get("_user", "unknown")
        root = shlex.quote(project if str(project).startswith('/') else f"/a0/usr/projects/{project}")
        message = args.get("message") or 'workflow repo sync'
        cmd = (
            f"cd {root} && "
            "git fetch origin && "
            "git add -A && "
            f"(git commit -m {shlex.quote(message)} || true) && "
            "(git push origin $(git branch --show-current) || (git pull --rebase origin $(git branch --show-current) && git push origin $(git branch --show-current)))"
        )
        result = await toolset.ssh.execute(cmd, user=user, timeout=int(args.get('timeout', 90)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def full_fix_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        root = _project_root(args.get("project"), args.get("project_root"))
        path = args.get("path")
        search = args.get("search")
        replace = args.get("replace")
        service = args.get("service")
        port = args.get("port")
        message = args.get("message") or "full fix workflow"
        user = args.get("_user", "unknown")
        code = (
            "from pathlib import Path; import shutil, sys; "
            f"p=Path({json.dumps(path)}); "
            "backup=str(p)+'.fullfix.bak'; shutil.copy2(p, backup); "
            f"s={json.dumps(search)}; r={json.dumps(replace)}; "
            "t=p.read_text(); c=t.count(s); print('BACKUP', backup); print('REPLACEMENTS', c); "
            "sys.exit(3) if c == 0 else None; p.write_text(t.replace(s,r))"
        )
        parts = [
            f"cd {shlex.quote(root)}",
            "echo '== BEFORE GIT STATUS ==' && git status --short || true",
            f"echo '== EDIT ==' && python3 -c {shlex.quote(code)}",
        ]
        parts.extend(_optional_service_parts(service))
        parts.extend(_optional_port_parts(port))
        parts.extend([
            f"echo '== GIT ADD ==' && git add -- {shlex.quote(path)}",
            f"echo '== GIT COMMIT ==' && (git commit -m {shlex.quote(message)} || true)",
            "echo '== GIT PUSH ==' && (git push origin $(git branch --show-current) || (git pull --rebase origin $(git branch --show-current) && git push origin $(git branch --show-current))) || true",
            "echo '== AFTER GIT STATUS ==' && git status --short || true",
        ])
        result = await toolset.ssh.execute(" && ".join(parts), user=user, use_sudo=bool(args.get("use_sudo", False)), timeout=int(args.get("timeout", 180)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def full_deploy_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        root = _project_root(args.get("project"), args.get("project_root"))
        service = args.get("service")
        port = args.get("port")
        pre_command = args.get("pre_command")
        deploy_command = args.get("deploy_command") or args.get("build_command")
        post_command = args.get("post_command")
        user = args.get("_user", "unknown")
        parts = [
            f"cd {shlex.quote(root)}",
            "echo '== REPO ==' && git branch --show-current && git rev-parse --short HEAD && git status --short || true",
        ]
        if pre_command:
            parts.append(f"echo '== PRE ==' && {pre_command}")
        if deploy_command:
            parts.append(f"echo '== DEPLOY ==' && {deploy_command}")
        parts.extend(_optional_service_parts(service))
        if post_command:
            parts.append(f"echo '== POST ==' && {post_command}")
        parts.extend(_optional_port_parts(port))
        result = await toolset.ssh.execute(" && ".join(parts), user=user, use_sudo=bool(args.get("use_sudo", False)), timeout=int(args.get("timeout", 240)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def full_repo_sync_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        root = _project_root(args.get("project"), args.get("project_root"))
        message = args.get("message") or "full repo sync workflow"
        user = args.get("_user", "unknown")
        parts = [
            f"cd {shlex.quote(root)}",
            "echo '== HEAD ==' && git branch --show-current && git rev-parse --short HEAD || true",
            "echo '== BEFORE ==' && git status --short || true",
            "echo '== FETCH ==' && git fetch origin || true",
            "echo '== ADD ==' && git add -A",
            f"echo '== COMMIT ==' && (git commit -m {shlex.quote(message)} || true)",
            "echo '== PUSH ==' && (git push origin $(git branch --show-current) || (git pull --rebase origin $(git branch --show-current) && git push origin $(git branch --show-current))) || true",
            "echo '== AFTER ==' && git status --short || true",
        ]
        result = await toolset.ssh.execute(" && ".join(parts), user=user, timeout=int(args.get('timeout', 180)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def full_debug_and_fix_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        root = _project_root(args.get("project"), args.get("project_root"))
        service = args.get("service")
        port = args.get("port")
        path = args.get("path")
        search = args.get("search")
        replace = args.get("replace")
        message = args.get("message") or "full debug and fix workflow"
        user = args.get("_user", "unknown")
        parts = [f"cd {shlex.quote(root)}"]
        if service:
            qservice = shlex.quote(service)
            parts.extend([
                f"echo '== BEFORE ACTIVE ==' && systemctl is-active {qservice} || true",
                f"echo '== BEFORE STATUS ==' && systemctl status {qservice} --no-pager | sed -n '1,25p' || true",
                f"echo '== BEFORE LOGS ==' && journalctl -u {qservice} -n 80 --no-pager || true",
            ])
        if port:
            parts.extend(_optional_port_parts(port))
        if path and search is not None and replace is not None:
            code = (
                "from pathlib import Path; import shutil; "
                f"p=Path({json.dumps(path)}); "
                "backup=str(p)+'.full-debug-fix.bak'; shutil.copy2(p, backup); "
                f"s={json.dumps(search)}; r={json.dumps(replace)}; "
                "t=p.read_text(); c=t.count(s); p.write_text(t.replace(s,r)); print('BACKUP', backup); print('REPLACEMENTS', c)"
            )
            parts.append(f"echo '== EDIT ==' && python3 -c {shlex.quote(code)}")
        parts.extend(_optional_service_parts(service))
        parts.extend(_optional_port_parts(port))
        parts.extend([
            "echo '== GIT STATUS ==' && git status --short || true",
            "echo '== GIT ADD ==' && git add -A",
            f"echo '== GIT COMMIT ==' && (git commit -m {shlex.quote(message)} || true)",
            "echo '== GIT PUSH ==' && (git push origin $(git branch --show-current) || (git pull --rebase origin $(git branch --show-current) && git push origin $(git branch --show-current))) || true",
        ])
        result = await toolset.ssh.execute(" && ".join(parts), user=user, use_sudo=bool(args.get("use_sudo", False)), timeout=int(args.get("timeout", 240)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def full_service_recovery_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        service = args.get("service")
        port = args.get("port")
        root = _project_root(args.get("project"), args.get("project_root"))
        user = args.get("_user", "unknown")
        qservice = shlex.quote(service)
        parts = [
            f"cd {shlex.quote(root)}",
            f"echo '== ACTIVE BEFORE ==' && systemctl is-active {qservice} || true",
            f"echo '== STATUS BEFORE ==' && systemctl status {qservice} --no-pager | sed -n '1,25p' || true",
            f"echo '== LOGS BEFORE ==' && journalctl -u {qservice} -n 80 --no-pager || true",
            f"echo '== RESTART ==' && systemctl restart {qservice} && systemctl is-active {qservice} || true",
            f"echo '== STATUS AFTER ==' && systemctl status {qservice} --no-pager | sed -n '1,30p' || true",
            f"echo '== LOGS AFTER ==' && journalctl -u {qservice} -n 80 --no-pager || true",
        ]
        parts.extend(_optional_port_parts(port))
        result = await toolset.ssh.execute(" && ".join(parts), user=user, use_sudo=bool(args.get("use_sudo", False)), timeout=int(args.get("timeout", 180)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def full_project_maintenance_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        root = _project_root(args.get("project"), args.get("project_root"))
        service = args.get("service")
        port = args.get("port")
        pre_command = args.get("pre_command")
        post_command = args.get("post_command")
        message = args.get("message") or "full project maintenance workflow"
        user = args.get("_user", "unknown")
        parts = [
            f"cd {shlex.quote(root)}",
            "echo '== TREE ==' && find . -maxdepth 2 | sed -n '1,120p' || true",
            "echo '== DISK ==' && du -sh . || true",
            "echo '== GIT BEFORE ==' && git branch --show-current && git rev-parse --short HEAD && git status --short || true",
        ]
        if pre_command:
            parts.append(f"echo '== PRE ==' && {pre_command}")
        parts.extend(_optional_service_parts(service))
        parts.extend(_optional_port_parts(port))
        if post_command:
            parts.append(f"echo '== POST ==' && {post_command}")
        parts.extend([
            "echo '== GIT ADD ==' && git add -A",
            f"echo '== GIT COMMIT ==' && (git commit -m {shlex.quote(message)} || true)",
            "echo '== GIT PUSH ==' && (git push origin $(git branch --show-current) || (git pull --rebase origin $(git branch --show-current) && git push origin $(git branch --show-current))) || true",
            "echo '== GIT AFTER ==' && git status --short || true",
        ])
        result = await toolset.ssh.execute(" && ".join(parts), user=user, use_sudo=bool(args.get("use_sudo", False)), timeout=int(args.get("timeout", 240)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def full_hotfix_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        root = _project_root(args.get("project"), args.get("project_root"))
        service = args.get("service")
        port = args.get("port")
        path = args.get("path")
        search = args.get("search")
        replace = args.get("replace")
        message = args.get("message") or "hotfix"
        user = args.get("_user", "unknown")
        parts = [f"cd {shlex.quote(root)}", "echo '== HOTFIX START ==' && git status --short || true"]
        if path and search is not None and replace is not None:
            code = (
                "from pathlib import Path; import shutil; "
                f"p=Path({json.dumps(path)}); "
                "backup=str(p)+'.hotfix.bak'; shutil.copy2(p, backup); "
                f"s={json.dumps(search)}; r={json.dumps(replace)}; "
                "t=p.read_text(); c=t.count(s); p.write_text(t.replace(s,r)); print('BACKUP', backup); print('REPLACEMENTS', c)"
            )
            parts.append(f"echo '== HOTFIX EDIT ==' && python3 -c {shlex.quote(code)}")
        parts.extend(_optional_service_parts(service))
        parts.extend(_optional_port_parts(port))
        parts.extend([
            "echo '== HOTFIX ADD ==' && git add -A",
            f"echo '== HOTFIX COMMIT ==' && (git commit -m {shlex.quote(message)} || true)",
            "echo '== HOTFIX PUSH ==' && (git push origin $(git branch --show-current) || (git pull --rebase origin $(git branch --show-current) && git push origin $(git branch --show-current))) || true",
        ])
        result = await toolset.ssh.execute(" && ".join(parts), user=user, use_sudo=bool(args.get("use_sudo", False)), timeout=int(args.get("timeout", 180)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def full_release_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        root = _project_root(args.get("project"), args.get("project_root"))
        service = args.get("service")
        port = args.get("port")
        version = args.get("version")
        pre_command = args.get("pre_command")
        build_command = args.get("build_command") or args.get("deploy_command")
        post_command = args.get("post_command")
        tag = args.get("tag") or (f"v{version}" if version else None)
        message = args.get("message") or (f"release {version}" if version else "release")
        user = args.get("_user", "unknown")
        parts = [f"cd {shlex.quote(root)}", "echo '== RELEASE START ==' && git branch --show-current && git rev-parse --short HEAD && git status --short || true"]
        if pre_command:
            parts.append(f"echo '== RELEASE PRE ==' && {pre_command}")
        if build_command:
            parts.append(f"echo '== RELEASE BUILD ==' && {build_command}")
        parts.extend(_optional_service_parts(service))
        parts.extend(_optional_port_parts(port))
        if post_command:
            parts.append(f"echo '== RELEASE POST ==' && {post_command}")
        parts.extend([
            "echo '== RELEASE ADD ==' && git add -A",
            f"echo '== RELEASE COMMIT ==' && (git commit -m {shlex.quote(message)} || true)",
        ])
        if tag:
            parts.append(f"echo '== RELEASE TAG ==' && (git tag -f {shlex.quote(tag)} || true)")
        parts.append("echo '== RELEASE PUSH ==' && (git push origin $(git branch --show-current) || (git pull --rebase origin $(git branch --show-current) && git push origin $(git branch --show-current))) || true")
        if tag:
            parts.append(f"echo '== RELEASE PUSH TAG ==' && (git push origin {shlex.quote(tag)} --force || true)")
        result = await toolset.ssh.execute(" && ".join(parts), user=user, use_sudo=bool(args.get("use_sudo", False)), timeout=int(args.get("timeout", 300)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def full_incident_response_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        root = _project_root(args.get("project"), args.get("project_root"))
        service = args.get("service")
        port = args.get("port")
        path = args.get("path")
        search = args.get("search")
        replace = args.get("replace")
        rollback = bool(args.get("rollback", False))
        message = args.get("message") or "incident response"
        user = args.get("_user", "unknown")
        parts = [f"cd {shlex.quote(root)}", "echo '== INCIDENT START ==' && date -u && git status --short || true"]
        if service:
            qservice = shlex.quote(service)
            parts.extend([
                f"echo '== INCIDENT STATUS BEFORE ==' && systemctl status {qservice} --no-pager | sed -n '1,30p' || true",
                f"echo '== INCIDENT LOGS BEFORE ==' && journalctl -u {qservice} -n 120 --no-pager || true",
            ])
        parts.extend(_optional_port_parts(port))
        if rollback and path:
            parts.append(f"echo '== INCIDENT ROLLBACK ==' && ls -1t {shlex.quote(path)}.*.bak | head -1 | xargs -r -I{{}} cp {{}} {shlex.quote(path)}")
        elif path and search is not None and replace is not None:
            code = (
                "from pathlib import Path; import shutil; "
                f"p=Path({json.dumps(path)}); "
                "backup=str(p)+'.incident.bak'; shutil.copy2(p, backup); "
                f"s={json.dumps(search)}; r={json.dumps(replace)}; "
                "t=p.read_text(); c=t.count(s); p.write_text(t.replace(s,r)); print('BACKUP', backup); print('REPLACEMENTS', c)"
            )
            parts.append(f"echo '== INCIDENT EDIT ==' && python3 -c {shlex.quote(code)}")
        parts.extend(_optional_service_parts(service))
        parts.extend(_optional_port_parts(port))
        parts.extend([
            "echo '== INCIDENT GIT ADD ==' && git add -A",
            f"echo '== INCIDENT COMMIT ==' && (git commit -m {shlex.quote(message)} || true)",
            "echo '== INCIDENT PUSH ==' && (git push origin $(git branch --show-current) || (git pull --rebase origin $(git branch --show-current) && git push origin $(git branch --show-current))) || true",
        ])
        result = await toolset.ssh.execute(" && ".join(parts), user=user, use_sudo=bool(args.get("use_sudo", False)), timeout=int(args.get("timeout", 300)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def prepare_bulk_staging_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        root = _project_root(args.get("project"), args.get("project_root"))
        staging_id = args.get("staging_id") or str(int(time.time()))
        staging_root = f"{root}/.runtime/staging/{staging_id}"
        worktree = f"{staging_root}/worktree"
        user = args.get("_user", "unknown")
        excludes = [".git", ".runtime/staging", "venv", "node_modules", "__pycache__"]
        exclude_args = ' '.join(f"--exclude={shlex.quote(x)}" for x in excludes)
        cmd = (
            f"mkdir -p {shlex.quote(staging_root)} && "
            f"rsync -a {exclude_args} {shlex.quote(root)}/ {shlex.quote(worktree)}/ && "
            f"echo STAGING_ROOT={shlex.quote(staging_root)} && "
            f"echo WORKTREE={shlex.quote(worktree)} && "
            f"echo APPLY_HINT='use apply_bulk_staging_workflow with staging_path={worktree}'"
        )
        result = await toolset.ssh.execute(cmd, user=user, timeout=int(args.get('timeout', 120)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    async def apply_bulk_staging_workflow(args: Dict[str, Any]) -> Dict[str, Any]:
        root = _project_root(args.get("project"), args.get("project_root"))
        staging_path = args.get("staging_path")
        if not staging_path:
            return {"content": [{"type": "text", "text": "staging_path is required"}], "isError": True}
        user = args.get("_user", "unknown")
        service = args.get("service")
        port = args.get("port")
        delete = bool(args.get("delete_missing", False))
        delete_flag = " --delete" if delete else ""
        excludes = [".git", ".runtime/staging", "venv", "node_modules", "__pycache__"]
        exclude_args = ' '.join(f"--exclude={shlex.quote(x)}" for x in excludes)
        parts = [
            f"echo '== APPLY STAGING ==' && rsync -a{delete_flag} {exclude_args} {shlex.quote(staging_path)}/ {shlex.quote(root)}/",
        ]
        parts.extend(_optional_service_parts(service))
        parts.extend(_optional_port_parts(port))
        result = await toolset.ssh.execute(" && ".join(parts), user=user, use_sudo=bool(args.get("use_sudo", False)), timeout=int(args.get('timeout', 180)))
        return {"content": [{"type": "text", "text": result.stdout.strip() or result.stderr.strip()}], "isError": result.exit_code != 0}

    extra = [
        ExtraToolDefinition("debug_service_workflow", "Run a compact multi-step service debug workflow including status, logs, optional port, and optional health endpoints.", {"type": "object", "properties": {"service": {"type": "string"}, "port": {"type": "integer"}, "log_path": {"type": "string"}, "timeout": {"type": "integer", "default": 40}}, "required": ["service"]}, debug_service_workflow, False, _ro("Debug Service Workflow")),
        ExtraToolDefinition("safe_edit_workflow", "Back up a file, replace text, optionally restart a service, and optionally verify local health endpoints.", {"type": "object", "properties": {"path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "restart_service": {"type": "string"}, "verify_port": {"type": "integer"}, "verify_health": {"type": "boolean", "default": True}, "use_sudo": {"type": "boolean", "default": False}, "timeout": {"type": "integer", "default": 60}}, "required": ["path", "search", "replace"]}, safe_edit_workflow, False, _rw("Safe Edit Workflow", False)),
        ExtraToolDefinition("collect_project_diagnostics", "Collect a project-level diagnostics bundle including tree, disk, and optional service/port context.", {"type": "object", "properties": {"project_root": {"type": "string"}, "service_name": {"type": "string"}, "port": {"type": "integer"}, "timeout": {"type": "integer", "default": 40}}, "required": ["project_root"]}, collect_project_diagnostics, False, _ro("Collect Project Diagnostics")),
        ExtraToolDefinition("prepare_bulk_staging_workflow", "Create a staging worktree copy under .runtime/staging so MCP edits can be prepared in bulk and applied back in one batch.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "staging_id": {"type": "string"}, "timeout": {"type": "integer", "default": 120}}, "required": []}, prepare_bulk_staging_workflow, False, _rw("Prepare Bulk Staging Workflow", False)),
        ExtraToolDefinition("apply_bulk_staging_workflow", "Apply a prepared staging worktree back to the project in one batch, with optional service restart and health verification.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "staging_path": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "delete_missing": {"type": "boolean", "default": False}, "use_sudo": {"type": "boolean", "default": False}, "timeout": {"type": "integer", "default": 180}}, "required": ["staging_path"]}, apply_bulk_staging_workflow, False, _rw("Apply Bulk Staging Workflow", True)),
        ExtraToolDefinition("repo_sync_workflow", "Run a fetch/add/commit/push workflow for a repo with automatic pull --rebase fallback.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "message": {"type": "string"}, "timeout": {"type": "integer", "default": 90}}, "required": []}, repo_sync_workflow, False, _rw("Repo Sync Workflow", False)),
        ExtraToolDefinition("full_fix_workflow", "Run a one-shot fix workflow: edit a file, optionally restart a service, verify health, and sync git in one confirmed action.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean", "default": False}, "timeout": {"type": "integer", "default": 180}}, "required": ["path", "search", "replace"]}, full_fix_workflow, False, _rw("Full Fix Workflow", False)),
        ExtraToolDefinition("full_deploy_workflow", "Run a one-shot deploy workflow: optional pre command, deploy/build command, restart service, optional post command, and verify health.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "pre_command": {"type": "string"}, "deploy_command": {"type": "string"}, "build_command": {"type": "string"}, "post_command": {"type": "string"}, "use_sudo": {"type": "boolean", "default": False}, "timeout": {"type": "integer", "default": 240}}, "required": []}, full_deploy_workflow, False, _rw("Full Deploy Workflow", False)),
        ExtraToolDefinition("full_repo_sync_workflow", "Run a one-shot repo sync workflow with fetch, add, commit, push, and automatic pull --rebase fallback.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "message": {"type": "string"}, "timeout": {"type": "integer", "default": 180}}, "required": []}, full_repo_sync_workflow, False, _rw("Full Repo Sync Workflow", False)),
        ExtraToolDefinition("full_debug_and_fix_workflow", "Run one confirmed action for diagnose, optional edit, service restart, health verification, and git sync.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean", "default": False}, "timeout": {"type": "integer", "default": 240}}, "required": []}, full_debug_and_fix_workflow, False, _rw("Full Debug And Fix Workflow", False)),
        ExtraToolDefinition("full_service_recovery_workflow", "Run one confirmed action for service diagnosis, restart, log capture, and optional health verification.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "use_sudo": {"type": "boolean", "default": False}, "timeout": {"type": "integer", "default": 180}}, "required": ["service"]}, full_service_recovery_workflow, False, _rw("Full Service Recovery Workflow", False)),
        ExtraToolDefinition("full_project_maintenance_workflow", "Run one confirmed action for project inspection, optional maintenance commands, service verification, and repo sync.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "pre_command": {"type": "string"}, "post_command": {"type": "string"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean", "default": False}, "timeout": {"type": "integer", "default": 240}}, "required": []}, full_project_maintenance_workflow, False, _rw("Full Project Maintenance Workflow", False)),
        ExtraToolDefinition("full_hotfix_workflow", "Run one confirmed hotfix action: patch a file, restart/verify service, and sync repo fast.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean", "default": False}, "timeout": {"type": "integer", "default": 180}}, "required": ["path", "search", "replace"]}, full_hotfix_workflow, False, _rw("Full Hotfix Workflow", False)),
        ExtraToolDefinition("full_release_workflow", "Run one confirmed release action: optional pre/build/post, restart/verify service, commit, tag, and push.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "version": {"type": "string"}, "tag": {"type": "string"}, "pre_command": {"type": "string"}, "build_command": {"type": "string"}, "deploy_command": {"type": "string"}, "post_command": {"type": "string"}, "message": {"type": "string"}, "use_sudo": {"type": "boolean", "default": False}, "timeout": {"type": "integer", "default": 300}}, "required": []}, full_release_workflow, False, _rw("Full Release Workflow", False)),
        ExtraToolDefinition("full_incident_response_workflow", "Run one confirmed incident-response action: capture status/logs, optional rollback or patch, restart/verify service, and sync repo.", {"type": "object", "properties": {"project": {"type": "string"}, "project_root": {"type": "string"}, "service": {"type": "string"}, "port": {"type": "integer"}, "path": {"type": "string"}, "search": {"type": "string"}, "replace": {"type": "string"}, "rollback": {"type": "boolean", "default": False}, "message": {"type": "string"}, "use_sudo": {"type": "boolean", "default": False}, "timeout": {"type": "integer", "default": 300}}, "required": []}, full_incident_response_workflow, False, _rw("Full Incident Response Workflow", False)),
    ]

    for tool in extra:
        toolset._register_tool(tool)

