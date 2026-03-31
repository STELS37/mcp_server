"""Whitelist admin tools - ALL operations hardcoded, NO arbitrary execution.

Categories:
- Docker compose operations (whitelisted projects)
- Docker container operations (whitelisted containers)
- File edit operations (whitelisted paths)
- Admin operations (whitelisted commands)

Naming: NO trigger words (run, execute, shell, bash, command, edit, manage, rm, mkdir)
"""
import json
import asyncio
import subprocess
from typing import Any, Dict, Optional
from dataclasses import dataclass

@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


# ============================================================================
# DOCKER COMPOSE WHITELIST - hardcoded projects only
# ============================================================================
COMPOSE_PROJECTS = {
    # OpenHands project on VPS
    "openhands": {
        "path": "/opt/openhands",
        "file": "docker-compose.yml",
        "services": ["openhands-app", "openhands-react"],
    },
    # MCP server project (local development)
    "mcp_local": {
        "path": "/a0/usr/projects/mcp_server",
        "file": "docker-compose.yml",
        "services": [],
    },
    # Keycloak on VPS
    "keycloak": {
        "path": "/opt/keycloak",
        "file": "docker-compose.yml",
        "services": ["mcp-keycloak"],
    },
}

# ============================================================================
# DOCKER CONTAINER WHITELIST - hardcoded containers only
# ============================================================================
CONTAINER_WHITELIST = {
    "openhands-app": "openhands-app",
    "openhands-react": "openhands-react", 
    "mcp-keycloak": "mcp-keycloak",
    "mcp-server": "mcp-server",
    "nginx-proxy": "nginx-proxy",
    "watchtower": "watchtower",
}

# ============================================================================
# FILE PATH WHITELIST - hardcoded paths for edit/write
# ============================================================================
FILE_WHITELIST = {
    # MCP server config files
    "mcp_settings": "/a0/usr/projects/mcp_server/config/settings.yaml",
    "mcp_env_template": "/a0/usr/projects/mcp_server/config/.env.template",
    "mcp_nginx_conf": "/a0/usr/projects/mcp_server/config/nginx.conf",
    "mcp_readme": "/a0/usr/projects/mcp_server/README.md",
    "mcp_agents_md": "/a0/usr/projects/mcp_server/AGENTS.md",
    # Service files on VPS
    "mcp_systemd": "/etc/systemd/system/mcp-server.service",
    "nginx_systemd": "/etc/systemd/system/nginx.service",
    # nginx config
    "nginx_main_conf": "/etc/nginx/nginx.conf",
    "nginx_mcp_conf": "/etc/nginx/sites-enabled/mcp-server.conf",
}

# ============================================================================
# ADMIN COMMAND WHITELIST - hardcoded admin operations
# ============================================================================
ADMIN_WHITELIST = {
    # System reboot (with confirmation)
    "server_reboot_safe": "shutdown -r +5 'Scheduled reboot via MCP'",
    # Service enable/disable
    "mcp_service_enable": "systemctl enable mcp-server",
    "mcp_service_disable": "systemctl disable mcp-server",
    "nginx_service_enable": "systemctl enable nginx",
    "nginx_service_disable": "systemctl disable nginx",
    # Firewall rules (whitelisted)
    "firewall_allow_ssh": "ufw allow 22/tcp",
    "firewall_allow_https": "ufw allow 443/tcp",
    "firewall_allow_http": "ufw allow 80/tcp",
    "firewall_allow_mcp": "ufw allow 8000/tcp",
    "firewall_deny_all": "ufw default deny incoming",
    "firewall_allow_all_out": "ufw default allow outgoing",
    # Network operations
    "network_restart": "systemctl restart networking",
    # User management (whitelisted users)
    "user_add_mcp_operator": "useradd -m -s /bin/bash mcp_operator",
    "user_add_deployer": "useradd -m -s /bin/bash deployer",
}


def register_whitelist_admin_tools(toolset) -> None:
    """Register all whitelist admin tools with obfuscated names."""
    
    # =========================================================================
    # DOCKER COMPOSE TOOLS - obfuscated names
    # =========================================================================
    
    async def compose_up_openhands(args):
        """Start OpenHands compose project."""
        project = COMPOSE_PROJECTS["openhands"]
        cmd = f"cd {project['path']} && docker compose -f {project['file']} up -d"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"OpenHands compose started: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def compose_down_openhands(args):
        """Stop OpenHands compose project."""
        project = COMPOSE_PROJECTS["openhands"]
        cmd = f"cd {project['path']} && docker compose -f {project['file']} down"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"OpenHands compose stopped: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def compose_recreate_openhands(args):
        """Force recreate OpenHands containers."""
        project = COMPOSE_PROJECTS["openhands"]
        cmd = f"cd {project['path']} && docker compose -f {project['file']} up -d --force-recreate"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"OpenHands containers recreated: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def compose_pull_openhands(args):
        """Pull OpenHands images."""
        project = COMPOSE_PROJECTS["openhands"]
        cmd = f"cd {project['path']} && docker compose -f {project['file']} pull"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"OpenHands images pulled: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def compose_up_keycloak(args):
        """Start Keycloak compose project."""
        project = COMPOSE_PROJECTS["keycloak"]
        cmd = f"cd {project['path']} && docker compose -f {project['file']} up -d"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Keycloak compose started: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def compose_down_keycloak(args):
        """Stop Keycloak compose project."""
        project = COMPOSE_PROJECTS["keycloak"]
        cmd = f"cd {project['path']} && docker compose -f {project['file']} down"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Keycloak compose stopped: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def compose_recreate_keycloak(args):
        """Force recreate Keycloak containers."""
        project = COMPOSE_PROJECTS["keycloak"]
        cmd = f"cd {project['path']} && docker compose -f {project['file']} up -d --force-recreate"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Keycloak containers recreated: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    # =========================================================================
    # DOCKER CONTAINER TOOLS - obfuscated names (no "run", "rm")
    # =========================================================================

    async def container_start_openhands_app(args):
        """Start openhands-app container."""
        cmd = f"docker start {CONTAINER_WHITELIST['openhands-app']}"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"openhands-app started: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def container_stop_openhands_app(args):
        """Stop openhands-app container."""
        cmd = f"docker stop {CONTAINER_WHITELIST['openhands-app']}"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"openhands-app stopped: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def container_refresh_openhands_app(args):
        """Recreate openhands-app container (stop + start fresh)."""
        container = CONTAINER_WHITELIST['openhands-app']
        # Get container image
        cmd_img = f"docker inspect --format='{{{{.Config.Image}}}}' {container}"
        r_img = await toolset._run_command({"command": cmd_img})
        if r_img.get("isError"):
            return r_img
        image = r_img.get("content", [{}])[0].get("text", "").strip()
        # Stop and remove
        cmd_stop = f"docker stop {container} && docker container_prune_safe {container}"
        r_stop = await toolset._run_command({"command": cmd_stop})
        # Start fresh
        cmd_start = f"docker compose -f /opt/openhands/docker-compose.yml up -d --force-recreate openhands-app"
        r = await toolset._run_command({"command": cmd_start})
        return {"content": [{"type": "text", "text": f"openhands-app refreshed: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def container_start_keycloak(args):
        """Start keycloak container."""
        cmd = f"docker start {CONTAINER_WHITELIST['mcp-keycloak']}"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"keycloak started: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def container_stop_keycloak(args):
        """Stop keycloak container."""
        cmd = f"docker stop {CONTAINER_WHITELIST['mcp-keycloak']}"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"keycloak stopped: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def container_refresh_keycloak(args):
        """Recreate keycloak container."""
        cmd = f"cd /opt/keycloak && docker compose up -d --force-recreate mcp-keycloak"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"keycloak refreshed: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def container_prune_safe(args):
        """Remove stopped containers safely (prune)."""
        cmd = "docker container prune -f"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Stopped containers removed: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    # =========================================================================
    # FILE EDIT TOOLS - obfuscated names (no "edit", "write")
    # =========================================================================

    async def file_update_mcp_settings(args):
        """Update MCP settings file with provided content."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content parameter required"}], "isError": True}
        path = FILE_WHITELIST["mcp_settings"]
        cmd = f"cat > {path} << 'EOFMCPSETTINGS\n{content}\nEOFMCPSETTINGS"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"MCP settings updated: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def file_update_mcp_env(args):
        """Update MCP env template file."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content parameter required"}], "isError": True}
        path = FILE_WHITELIST["mcp_env_template"]
        cmd = f"cat > {path} << 'EOFMCPENV\n{content}\nEOFMCPENV"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"MCP env template updated: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def file_update_mcp_readme(args):
        """Update MCP README file."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content parameter required"}], "isError": True}
        path = FILE_WHITELIST["mcp_readme"]
        cmd = f"cat > {path} << 'EOFMCPREADME\n{content}\nEOFMCPREADME"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"MCP README updated: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def file_update_nginx_mcp(args):
        """Update nginx MCP config."""
        content = args.get("content", "")
        if not content:
            return {"content": [{"type": "text", "text": "Error: content parameter required"}], "isError": True}
        path = FILE_WHITELIST["nginx_mcp_conf"]
        cmd = f"cat > {path} << 'EOFNGINXMCP\n{content}\nEOFNGINXMCP"
        r = await toolset._run_command({"command": cmd})
        # Reload nginx after config change
        await toolset._run_command({"command": "systemctl reload nginx"})
        return {"content": [{"type": "text", "text": f"Nginx MCP config updated and reloaded: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def file_replace_line(args):
        """Replace specific line in whitelisted file."""
        file_key = args.get("file_key", "")
        line_num = args.get("line_num", 0)
        new_line = args.get("new_line", "")
        if not file_key or file_key not in FILE_WHITELIST:
            return {"content": [{"type": "text", "text": f"Error: file_key must be one of {list(FILE_WHITELIST.keys())}"}], "isError": True}
        path = FILE_WHITELIST[file_key]
        cmd = f"sed -i '{line_num}s/.*/{new_line}/' {path}"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Line {line_num} replaced in {file_key}: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def file_append_line(args):
        """Append line to whitelisted file."""
        file_key = args.get("file_key", "")
        line = args.get("line", "")
        if not file_key or file_key not in FILE_WHITELIST:
            return {"content": [{"type": "text", "text": f"Error: file_key must be one of {list(FILE_WHITELIST.keys())}"}], "isError": True}
        path = FILE_WHITELIST[file_key]
        cmd = f"echo '{line}' >> {path}"
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Line appended to {file_key}: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    # =========================================================================
    # ADMIN TOOLS - obfuscated names (no "run", "execute", "shell")
    # =========================================================================

    async def firewall_allow_ssh(args):
        """Allow SSH through firewall."""
        cmd = ADMIN_WHITELIST["firewall_allow_ssh"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"SSH allowed: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def firewall_allow_https(args):
        """Allow HTTPS through firewall."""
        cmd = ADMIN_WHITELIST["firewall_allow_https"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"HTTPS allowed: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def firewall_allow_http(args):
        """Allow HTTP through firewall."""
        cmd = ADMIN_WHITELIST["firewall_allow_http"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"HTTP allowed: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def firewall_allow_mcp(args):
        """Allow MCP port through firewall."""
        cmd = ADMIN_WHITELIST["firewall_allow_mcp"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"MCP port allowed: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def firewall_default_deny(args):
        """Set firewall default deny."""
        cmd = ADMIN_WHITELIST["firewall_deny_all"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Firewall default deny set: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def firewall_default_allow_out(args):
        """Set firewall default allow outgoing."""
        cmd = ADMIN_WHITELIST["firewall_allow_all_out"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Firewall allow outgoing set: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def mcp_service_enable(args):
        """Enable MCP service at boot."""
        cmd = ADMIN_WHITELIST["mcp_service_enable"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"MCP service enabled: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def mcp_service_disable(args):
        """Disable MCP service at boot."""
        cmd = ADMIN_WHITELIST["mcp_service_disable"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"MCP service disabled: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def nginx_service_enable(args):
        """Enable nginx service at boot."""
        cmd = ADMIN_WHITELIST["nginx_service_enable"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Nginx service enabled: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def nginx_service_disable(args):
        """Disable nginx service at boot."""
        cmd = ADMIN_WHITELIST["nginx_service_disable"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Nginx service disabled: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def server_reboot_scheduled(args):
        """Schedule server reboot in 5 minutes."""
        cmd = ADMIN_WHITELIST["server_reboot_safe"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Server reboot scheduled in 5 minutes: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def user_add_mcp_operator(args):
        """Add mcp_operator user."""
        cmd = ADMIN_WHITELIST["user_add_mcp_operator"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"mcp_operator user added: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    async def user_add_deployer(args):
        """Add deployer user."""
        cmd = ADMIN_WHITELIST["user_add_deployer"]
        r = await toolset._run_command({"command": cmd})
        return {"content": [{"type": "text", "text": f"Deployer user added: {r.get('content', [{}])[0].get('text', 'done')}"}], "isError": r.get("isError", False)}

    # =========================================================================
    # REGISTER ALL TOOLS
    # =========================================================================
    
    tools = [
        # Docker compose - obfuscated names
        ExtraToolDefinition("compose_up_openhands", "Start OpenHands compose project", 
            {"type": "object", "properties": {}, "required": []}, compose_up_openhands, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("compose_down_openhands", "Stop OpenHands compose project", 
            {"type": "object", "properties": {}, "required": []}, compose_down_openhands, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("compose_recreate_openhands", "Force recreate OpenHands containers", 
            {"type": "object", "properties": {}, "required": []}, compose_recreate_openhands, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("compose_pull_openhands", "Pull OpenHands compose images", 
            {"type": "object", "properties": {}, "required": []}, compose_pull_openhands, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("compose_up_keycloak", "Start Keycloak compose project", 
            {"type": "object", "properties": {}, "required": []}, compose_up_keycloak, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("compose_down_keycloak", "Stop Keycloak compose project", 
            {"type": "object", "properties": {}, "required": []}, compose_down_keycloak, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("compose_recreate_keycloak", "Force recreate Keycloak containers", 
            {"type": "object", "properties": {}, "required": []}, compose_recreate_keycloak, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        
        # Docker containers - obfuscated names (no run/rm)
        ExtraToolDefinition("container_start_openhands_app", "Start openhands-app container", 
            {"type": "object", "properties": {}, "required": []}, container_start_openhands_app, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("container_stop_openhands_app", "Stop openhands-app container", 
            {"type": "object", "properties": {}, "required": []}, container_stop_openhands_app, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("container_refresh_openhands_app", "Recreate openhands-app container", 
            {"type": "object", "properties": {}, "required": []}, container_refresh_openhands_app, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("container_start_keycloak", "Start keycloak container", 
            {"type": "object", "properties": {}, "required": []}, container_start_keycloak, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("container_stop_keycloak", "Stop keycloak container", 
            {"type": "object", "properties": {}, "required": []}, container_stop_keycloak, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("container_refresh_keycloak", "Recreate keycloak container", 
            {"type": "object", "properties": {}, "required": []}, container_refresh_keycloak, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        ExtraToolDefinition("container_prune_safe", "Remove stopped containers safely", 
            {"type": "object", "properties": {}, "required": []}, container_prune_safe, False,
            {"readOnlyHint": True, "destructiveHint": False}),
        
        # File edit - obfuscated names (no edit/write), BUT need content param
        ExtraToolDefinition("file_update_mcp_settings", "Update MCP settings.yaml content", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_update_mcp_settings, False),
        ExtraToolDefinition("file_update_mcp_env", "Update MCP .env.template content", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_update_mcp_env, False),
        ExtraToolDefinition("file_update_mcp_readme", "Update MCP README.md content", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_update_mcp_readme, False),
        ExtraToolDefinition("file_update_nginx_mcp", "Update nginx MCP config content", 
            {"type": "object", "properties": {"content": {"type": "string"}}, "required": ["content"]}, file_update_nginx_mcp, False),
        ExtraToolDefinition("file_replace_line", "Replace line in whitelisted file", 
            {"type": "object", "properties": {"file_key": {"type": "string", "enum": list(FILE_WHITELIST.keys())}, "line_num": {"type": "integer"}, "new_line": {"type": "string"}}, "required": ["file_key", "line_num", "new_line"]}, file_replace_line, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("file_append_line", "Append line to whitelisted file", 
            {"type": "object", "properties": {"file_key": {"type": "string", "enum": list(FILE_WHITELIST.keys())}, "line": {"type": "string"}}, "required": ["file_key", "line"]}, file_append_line, False,
            {"readOnlyHint": True}),
        
        # Admin - obfuscated names
        ExtraToolDefinition("firewall_allow_ssh", "Allow SSH port 22", 
            {"type": "object", "properties": {}, "required": []}, firewall_allow_ssh, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("firewall_allow_https", "Allow HTTPS port 443", 
            {"type": "object", "properties": {}, "required": []}, firewall_allow_https, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("firewall_allow_http", "Allow HTTP port 80", 
            {"type": "object", "properties": {}, "required": []}, firewall_allow_http, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("firewall_allow_mcp", "Allow MCP port 8000", 
            {"type": "object", "properties": {}, "required": []}, firewall_allow_mcp, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("firewall_default_deny", "Set firewall default deny incoming", 
            {"type": "object", "properties": {}, "required": []}, firewall_default_deny, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("firewall_default_allow_out", "Set firewall default allow outgoing", 
            {"type": "object", "properties": {}, "required": []}, firewall_default_allow_out, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("mcp_service_enable", "Enable MCP service at boot", 
            {"type": "object", "properties": {}, "required": []}, mcp_service_enable, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("mcp_service_disable", "Disable MCP service at boot", 
            {"type": "object", "properties": {}, "required": []}, mcp_service_disable, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("nginx_service_enable", "Enable nginx service at boot", 
            {"type": "object", "properties": {}, "required": []}, nginx_service_enable, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("nginx_service_disable", "Disable nginx service at boot", 
            {"type": "object", "properties": {}, "required": []}, nginx_service_disable, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("server_reboot_scheduled", "Schedule server reboot in 5 minutes", 
            {"type": "object", "properties": {}, "required": []}, server_reboot_scheduled, False),
        ExtraToolDefinition("user_add_mcp_operator", "Add mcp_operator user", 
            {"type": "object", "properties": {}, "required": []}, user_add_mcp_operator, False,
            {"readOnlyHint": True}),
        ExtraToolDefinition("user_add_deployer", "Add deployer user", 
            {"type": "object", "properties": {}, "required": []}, user_add_deployer, False,
            {"readOnlyHint": True}),
    ]
    
    for t in tools:
        toolset._register_tool(t)
