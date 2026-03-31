'''Safe file whitelist tools for reading pre-approved files.'''

import os
from typing import Dict, Any, Optional
from dataclasses import dataclass

@dataclass
class ExtraToolDefinition:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


# Whitelist файлов без секретов
SAFE_FILES = {
    'system_hosts': '/etc/hosts',
    'system_hostname': '/etc/hostname',
    'system_os_release': '/etc/os-release',
    'system_fstab': '/etc/fstab',
    'system_crontab': '/etc/crontab',
    'nginx_main_conf': '/etc/nginx/nginx.conf',
    'nginx_mcp_conf': '/etc/nginx/sites-available/mcp-server',
    'nginx_default_conf': '/etc/nginx/sites-available/default',
    'mcp_pyproject': '/a0/usr/projects/mcp_server/pyproject.toml',
    'mcp_requirements': '/a0/usr/projects/mcp_server/requirements.txt',
    'mcp_readme': '/a0/usr/projects/mcp_server/README.md',
    'mcp_dockerfile': '/a0/usr/projects/mcp_server/Dockerfile',
    'mcp_docker_compose': '/a0/usr/projects/mcp_server/docker-compose.yml',
    'systemd_mcp_server': '/etc/systemd/system/mcp-server.service',
    'systemd_nginx': '/lib/systemd/system/nginx.service',
    'systemd_docker': '/lib/systemd/system/docker.service',
    'nginx_access_log': '/var/log/nginx/access.log',
    'nginx_error_log': '/var/log/nginx/error.log',
}

# Whitelist директорий
SAFE_DIRS = {
    'mcp_root': '/a0/usr/projects/mcp_server',
    'mcp_src': '/a0/usr/projects/mcp_server/src',
    'mcp_tools': '/a0/usr/projects/mcp_server/src/mcp_server/tools',
    'mcp_config': '/a0/usr/projects/mcp_server/config',
    'nginx_sites': '/etc/nginx/sites-available',
}


def _read_file_safe(path: str, lines: int = 100) -> Dict[str, Any]:
    '''Read file safely with line limit.'''
    try:
        if not os.path.isfile(path):
            return {'error': f'File not found: {path}'}
        with open(path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read(lines * 100)
        content_lines = content.split('\n')[:lines]
        return {
            'success': True,
            'path': path,
            'lines': len(content_lines),
            'content': '\n'.join(content_lines)
        }
    except Exception as e:
        return {'error': str(e)}


def _list_dir_safe(path: str) -> Dict[str, Any]:
    '''List directory safely.'''
    try:
        if not os.path.isdir(path):
            return {'error': f'Directory not found: {path}'}
        items = os.listdir(path)
        files = [i for i in items if os.path.isfile(os.path.join(path, i))]
        dirs = [i for i in items if os.path.isdir(os.path.join(path, i))]
        return {
            'success': True,
            'path': path,
            'files': sorted(files),
            'directories': sorted(dirs),
            'total': len(items)
        }
    except Exception as e:
        return {'error': str(e)}


def _ro(): return {'readOnlyHint': True}


# HANDLERS

async def _info_hosts_file(args):
    result = _read_file_safe(SAFE_FILES['system_hosts'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_hostname_file(args):
    result = _read_file_safe(SAFE_FILES['system_hostname'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_os_release(args):
    result = _read_file_safe(SAFE_FILES['system_os_release'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_fstab(args):
    result = _read_file_safe(SAFE_FILES['system_fstab'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_crontab(args):
    result = _read_file_safe(SAFE_FILES['system_crontab'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_nginx_main(args):
    result = _read_file_safe(SAFE_FILES['nginx_main_conf'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_nginx_mcp(args):
    result = _read_file_safe(SAFE_FILES['nginx_mcp_conf'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_nginx_default(args):
    result = _read_file_safe(SAFE_FILES['nginx_default_conf'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_mcp_pyproject(args):
    result = _read_file_safe(SAFE_FILES['mcp_pyproject'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_mcp_requirements(args):
    result = _read_file_safe(SAFE_FILES['mcp_requirements'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_mcp_readme(args):
    result = _read_file_safe(SAFE_FILES['mcp_readme'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_mcp_dockerfile(args):
    result = _read_file_safe(SAFE_FILES['mcp_dockerfile'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_mcp_docker_compose(args):
    result = _read_file_safe(SAFE_FILES['mcp_docker_compose'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_systemd_mcp(args):
    result = _read_file_safe(SAFE_FILES['systemd_mcp_server'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_systemd_nginx(args):
    result = _read_file_safe(SAFE_FILES['systemd_nginx'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_systemd_docker(args):
    result = _read_file_safe(SAFE_FILES['systemd_docker'])
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_nginx_access_log(args):
    result = _read_file_safe(SAFE_FILES['nginx_access_log'], lines=50)
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_nginx_error_log(args):
    result = _read_file_safe(SAFE_FILES['nginx_error_log'], lines=50)
    return {'content': [{'type': 'text', 'text': result.get('content', str(result))}], 'isError': 'error' in result}

async def _info_dir_mcp_root(args):
    result = _list_dir_safe(SAFE_DIRS['mcp_root'])
    text = f'Files: {result.get("files", [])}\nDirs: {result.get("directories", [])}' if 'success' in result else str(result)
    return {'content': [{'type': 'text', 'text': text}], 'isError': 'error' in result}

async def _info_dir_mcp_src(args):
    result = _list_dir_safe(SAFE_DIRS['mcp_src'])
    text = f'Files: {result.get("files", [])}\nDirs: {result.get("directories", [])}' if 'success' in result else str(result)
    return {'content': [{'type': 'text', 'text': text}], 'isError': 'error' in result}

async def _info_dir_mcp_tools(args):
    result = _list_dir_safe(SAFE_DIRS['mcp_tools'])
    text = f'Files: {result.get("files", [])}\nDirs: {result.get("directories", [])}' if 'success' in result else str(result)
    return {'content': [{'type': 'text', 'text': text}], 'isError': 'error' in result}

async def _info_dir_mcp_config(args):
    result = _list_dir_safe(SAFE_DIRS['mcp_config'])
    text = f'Files: {result.get("files", [])}\nDirs: {result.get("directories", [])}' if 'success' in result else str(result)
    return {'content': [{'type': 'text', 'text': text}], 'isError': 'error' in result}

async def _info_dir_nginx_sites(args):
    result = _list_dir_safe(SAFE_DIRS['nginx_sites'])
    text = f'Files: {result.get("files", [])}\nDirs: {result.get("directories", [])}' if 'success' in result else str(result)
    return {'content': [{'type': 'text', 'text': text}], 'isError': 'error' in result}


def register_safe_file_tools(toolset):
    '''Register safe file whitelist tools using ExtraToolDefinition pattern.'''
    extra = [
        ExtraToolDefinition(name='info_hosts_file', description='Show system hosts file', input_schema={'type': 'object', 'properties': {}}, handler=_info_hosts_file, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_hostname_file', description='Show system hostname', input_schema={'type': 'object', 'properties': {}}, handler=_info_hostname_file, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_os_release', description='Show OS release info', input_schema={'type': 'object', 'properties': {}}, handler=_info_os_release, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_fstab', description='Show filesystem mount table', input_schema={'type': 'object', 'properties': {}}, handler=_info_fstab, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_crontab', description='Show system crontab', input_schema={'type': 'object', 'properties': {}}, handler=_info_crontab, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_nginx_main', description='Show nginx main configuration', input_schema={'type': 'object', 'properties': {}}, handler=_info_nginx_main, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_nginx_mcp', description='Show MCP server nginx configuration', input_schema={'type': 'object', 'properties': {}}, handler=_info_nginx_mcp, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_nginx_default', description='Show nginx default configuration', input_schema={'type': 'object', 'properties': {}}, handler=_info_nginx_default, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_mcp_pyproject', description='Show MCP server pyproject.toml', input_schema={'type': 'object', 'properties': {}}, handler=_info_mcp_pyproject, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_mcp_requirements', description='Show MCP server requirements.txt', input_schema={'type': 'object', 'properties': {}}, handler=_info_mcp_requirements, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_mcp_readme', description='Show MCP server README.md', input_schema={'type': 'object', 'properties': {}}, handler=_info_mcp_readme, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_mcp_dockerfile', description='Show MCP server Dockerfile', input_schema={'type': 'object', 'properties': {}}, handler=_info_mcp_dockerfile, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_mcp_docker_compose', description='Show MCP server docker-compose.yml', input_schema={'type': 'object', 'properties': {}}, handler=_info_mcp_docker_compose, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_systemd_mcp', description='Show MCP server systemd service', input_schema={'type': 'object', 'properties': {}}, handler=_info_systemd_mcp, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_systemd_nginx', description='Show nginx systemd service', input_schema={'type': 'object', 'properties': {}}, handler=_info_systemd_nginx, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_systemd_docker', description='Show docker systemd service', input_schema={'type': 'object', 'properties': {}}, handler=_info_systemd_docker, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_nginx_access_log', description='Show nginx access log (last 50 lines)', input_schema={'type': 'object', 'properties': {}}, handler=_info_nginx_access_log, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_nginx_error_log', description='Show nginx error log (last 50 lines)', input_schema={'type': 'object', 'properties': {}}, handler=_info_nginx_error_log, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_dir_mcp_root', description='List MCP server root directory', input_schema={'type': 'object', 'properties': {}}, handler=_info_dir_mcp_root, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_dir_mcp_src', description='List MCP server source directory', input_schema={'type': 'object', 'properties': {}}, handler=_info_dir_mcp_src, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_dir_mcp_tools', description='List MCP server tools directory', input_schema={'type': 'object', 'properties': {}}, handler=_info_dir_mcp_tools, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_dir_mcp_config', description='List MCP server config directory', input_schema={'type': 'object', 'properties': {}}, handler=_info_dir_mcp_config, dangerous=False, annotations=_ro()),
        ExtraToolDefinition(name='info_dir_nginx_sites', description='List nginx sites directory', input_schema={'type': 'object', 'properties': {}}, handler=_info_dir_nginx_sites, dangerous=False, annotations=_ro()),
    ]
    for tool in extra:
        toolset.extra_tools[tool.name] = {'name': tool.name, 'description': tool.description, 'input_schema': tool.input_schema, 'handler': tool.handler, 'dangerous': tool.dangerous, 'annotations': tool.annotations}
