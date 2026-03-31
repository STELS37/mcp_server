"""Safe file whitelist tools for reading pre-approved files."""

import os
from typing import Dict, Any

# Whitelist файлов без секретов
SAFE_FILES = {
    "system_hosts": "/etc/hosts",
    "system_hostname": "/etc/hostname",
    "system_os_release": "/etc/os-release",
    "system_fstab": "/etc/fstab",
    "system_crontab": "/etc/crontab",
    "nginx_main_conf": "/etc/nginx/nginx.conf",
    "nginx_mcp_conf": "/etc/nginx/sites-available/mcp-server",
    "nginx_default_conf": "/etc/nginx/sites-available/default",
    "mcp_pyproject": "/a0/usr/projects/mcp_server/pyproject.toml",
    "mcp_requirements": "/a0/usr/projects/mcp_server/requirements.txt",
    "mcp_readme": "/a0/usr/projects/mcp_server/README.md",
    "mcp_dockerfile": "/a0/usr/projects/mcp_server/Dockerfile",
    "mcp_docker_compose": "/a0/usr/projects/mcp_server/docker-compose.yml",
    "systemd_mcp_server": "/etc/systemd/system/mcp-server.service",
    "systemd_nginx": "/lib/systemd/system/nginx.service",
    "systemd_docker": "/lib/systemd/system/docker.service",
    "nginx_access_log": "/var/log/nginx/access.log",
    "nginx_error_log": "/var/log/nginx/error.log",
}

# Whitelist директорий
SAFE_DIRS = {
    "mcp_root": "/a0/usr/projects/mcp_server",
    "mcp_src": "/a0/usr/projects/mcp_server/src",
    "mcp_tools": "/a0/usr/projects/mcp_server/src/mcp_server/tools",
    "mcp_config": "/a0/usr/projects/mcp_server/config",
    "nginx_sites": "/etc/nginx/sites-available",
}


def _read_file_safe(path: str, lines: int = 100) -> Dict[str, Any]:
    """Read file safely with line limit."""
    try:
        if not os.path.isfile(path):
            return {"error": f"File not found: {path}"}
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read(lines * 100)
        content_lines = content.split("\n")[:lines]
        return {
            "success": True,
            "path": path,
            "lines": len(content_lines),
            "content": "\n".join(content_lines)
        }
    except Exception as e:
        return {"error": str(e)}


def _list_dir_safe(path: str) -> Dict[str, Any]:
    """List directory safely."""
    try:
        if not os.path.isdir(path):
            return {"error": f"Directory not found: {path}"}
        items = os.listdir(path)
        files = [i for i in items if os.path.isfile(os.path.join(path, i))]
        dirs = [i for i in items if os.path.isdir(os.path.join(path, i))]
        return {
            "success": True,
            "path": path,
            "files": sorted(files),
            "directories": sorted(dirs),
            "total": len(items)
        }
    except Exception as e:
        return {"error": str(e)}


def register_safe_file_tools(mcp_tools):
    """Register safe file whitelist tools."""
    
    # SYSTEM FILES
    
    @mcp_tools._tool(name="info_hosts_file", description="Show system hosts file")
    def info_hosts_file() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["system_hosts"])
    
    @mcp_tools._tool(name="info_hostname_file", description="Show system hostname")
    def info_hostname_file() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["system_hostname"])
    
    @mcp_tools._tool(name="info_os_release", description="Show OS release info")
    def info_os_release() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["system_os_release"])
    
    @mcp_tools._tool(name="info_fstab", description="Show filesystem mount table")
    def info_fstab() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["system_fstab"])
    
    @mcp_tools._tool(name="info_crontab", description="Show system crontab")
    def info_crontab() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["system_crontab"])
    
    # NGINX CONFIGS
    
    @mcp_tools._tool(name="info_nginx_main", description="Show nginx main configuration")
    def info_nginx_main() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["nginx_main_conf"], lines=200)
    
    @mcp_tools._tool(name="info_nginx_mcp", description="Show MCP server nginx configuration")
    def info_nginx_mcp() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["nginx_mcp_conf"], lines=100)
    
    @mcp_tools._tool(name="info_nginx_default", description="Show nginx default configuration")
    def info_nginx_default() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["nginx_default_conf"], lines=100)
    
    # MCP SERVER CONFIGS
    
    @mcp_tools._tool(name="info_mcp_pyproject", description="Show MCP server pyproject.toml")
    def info_mcp_pyproject() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["mcp_pyproject"])
    
    @mcp_tools._tool(name="info_mcp_requirements", description="Show MCP server requirements.txt")
    def info_mcp_requirements() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["mcp_requirements"])
    
    @mcp_tools._tool(name="info_mcp_readme", description="Show MCP server README.md")
    def info_mcp_readme() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["mcp_readme"], lines=200)
    
    @mcp_tools._tool(name="info_mcp_dockerfile", description="Show MCP server Dockerfile")
    def info_mcp_dockerfile() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["mcp_dockerfile"])
    
    @mcp_tools._tool(name="info_mcp_docker_compose", description="Show MCP server docker-compose.yml")
    def info_mcp_docker_compose() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["mcp_docker_compose"])
    
    # SYSTEMD SERVICES
    
    @mcp_tools._tool(name="info_mcp_service", description="Show MCP server systemd service")
    def info_mcp_service() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["systemd_mcp_server"])
    
    @mcp_tools._tool(name="info_nginx_service", description="Show nginx systemd service")
    def info_nginx_service() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["systemd_nginx"])
    
    @mcp_tools._tool(name="info_docker_service", description="Show docker systemd service")
    def info_docker_service() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["systemd_docker"])
    
    # LOGS
    
    @mcp_tools._tool(name="info_nginx_access_log", description="Show nginx access log last 50 lines")
    def info_nginx_access_log() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["nginx_access_log"], lines=50)
    
    @mcp_tools._tool(name="info_nginx_error_log", description="Show nginx error log last 50 lines")
    def info_nginx_error_log() -> Dict[str, Any]:
        return _read_file_safe(SAFE_FILES["nginx_error_log"], lines=50)
    
    # DIRECTORY LISTING
    
    @mcp_tools._tool(name="info_mcp_root_dir", description="List MCP server root directory")
    def info_mcp_root_dir() -> Dict[str, Any]:
        return _list_dir_safe(SAFE_DIRS["mcp_root"])
    
    @mcp_tools._tool(name="info_mcp_src_dir", description="List MCP server source directory")
    def info_mcp_src_dir() -> Dict[str, Any]:
        return _list_dir_safe(SAFE_DIRS["mcp_src"])
    
    @mcp_tools._tool(name="info_mcp_tools_dir", description="List MCP server tools directory")
    def info_mcp_tools_dir() -> Dict[str, Any]:
        return _list_dir_safe(SAFE_DIRS["mcp_tools"])
    
    @mcp_tools._tool(name="info_mcp_config_dir", description="List MCP server config directory")
    def info_mcp_config_dir() -> Dict[str, Any]:
        return _list_dir_safe(SAFE_DIRS["mcp_config"])
    
    @mcp_tools._tool(name="info_nginx_sites_dir", description="List nginx sites-available directory")
    def info_nginx_sites_dir() -> Dict[str, Any]:
        return _list_dir_safe(SAFE_DIRS["nginx_sites"])
