# MCP SSH Gateway - Remote MCP Server for ChatGPT

A production-ready remote MCP (Model Context Protocol) server that enables ChatGPT to execute commands and manage files on your VPS through a secure SSH gateway.

## Architecture

```
┌─────────────┐     HTTPS/SSE      ┌──────────────────┐     SSH      ┌────────────────────┐
│   ChatGPT   │ ◄─────────────────► │  Management VPS  │ ◄──────────► │ Experimental VPS   │
│             │                     │   MCP Server     │              │   (Your Server)    │
│  (OAuth)    │                     │   - OAuth/OIDC   │              │   - SSH Access     │
│             │                     │   - Rate Limit   │              │   - Root/Sudo      │
│             │                     │   - Logging      │              │                    │
└─────────────┘                     └──────────────────┘              └────────────────────┘
                                          ▲                                    ▲
                                          │                                    │
                                    Nginx/HTTPS                          IP Restricted
                                    TLS 1.3                              SSH Key Only
```

## Features

- **Remote MCP Server**: ChatGPT-compatible SSE endpoint
- **OAuth/OIDC Authentication**: With refresh token support
- **SSH Gateway**: Execute commands on experimental VPS
- **Safety Safeguards**: Dangerous commands require confirmation
- **Comprehensive Logging**: All tool calls logged
- **Rate Limiting**: Protection against abuse
- **Health Checks**: `/health` and `/ready` endpoints

## Quick Start

### Prerequisites

- Management VPS (public IP, domain)
- Experimental VPS (can be private, accessible via SSH)
- Domain name for MCP server (e.g., `mcp.yourdomain.com`)
- OAuth provider (Auth0, Keycloak, Google, etc.)

### Deployment Steps

1. **Clone and configure**:
```bash
git clone <repo-url> /opt/mcp-server
cd /opt/mcp-server
cp config/.env.template .env
# Edit .env with your configuration
```

2. **Run deployment script**:
```bash
sudo scripts/deploy.sh
```

3. **Configure experimental VPS**:
```bash
# On experimental VPS
sudo MANAGEMENT_VPS_IP=<management-vps-ip> scripts/setup-experimental-vps.sh

# Add MCP server's SSH public key to authorized_keys
cat /opt/mcp-server/secrets/ssh_key.pub  # On Management VPS
# Add this to ~/.ssh/authorized_keys on Experimental VPS
```

4. **Configure OAuth provider**:
- Create an application in your OAuth provider
- Set redirect URI: `https://mcp.yourdomain.com/auth/callback`
- Enable `offline_access` for refresh tokens
- Copy client ID and secret to `.env`

5. **Start and verify**:
```bash
sudo systemctl start mcp-server
sudo systemctl status mcp-server
curl https://mcp.yourdomain.com/health
```

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `MCP_BASE_URL` | Public URL of MCP server | Yes |
| `MCP_SSH__HOST` | Experimental VPS IP/hostname | Yes |
| `MCP_SSH__USER` | SSH username | Yes |
| `MCP_OAUTH__ISSUER_URL` | OAuth issuer URL | Yes |
| `MCP_OAUTH__CLIENT_ID` | OAuth client ID | Yes |
| `MCP_OAUTH__CLIENT_SECRET` | OAuth client secret | Yes |

See `.env.template` for all options.

## MCP Tools

The following tools are exposed to ChatGPT:

| Tool | Description | Dangerous |
|------|-------------|----------|
| `ping_host` | Ping a host from VPS | No |
| `run_command` | Execute shell command | Yes* |
| `read_file` | Read file contents | No |
| `write_file` | Write to file | Yes |
| `upload_file` | Upload file (base64) | Yes |
| `download_file` | Download file (base64) | No |
| `list_dir` | List directory contents | No |
| `systemd_status` | Get service status | No |
| `systemd_restart` | Restart service | Yes |
| `journal_tail` | View journal logs | No |
| `docker_ps` | List containers | No |
| `docker_logs` | View container logs | No |
| `docker_exec` | Execute in container | Yes |
| `get_public_ip` | Get VPS public IP | No |
| `get_server_facts` | Get server info | No |

*Dangerous commands require `confirm=true` parameter.

### Dangerous Commands

These commands require explicit confirmation:
- `reboot`, `shutdown`, `halt`, `poweroff`
- `rm -rf`, `rm -r`, `rm -R`
- `ufw`, `iptables`, `firewall-cmd`
- `userdel`, `useradd`, `passwd`
- `systemctl` (restart, stop, disable)
- `docker` (rm, rmi, stop, kill)
- Any command matching dangerous patterns

## ChatGPT Integration

### Final Values for ChatGPT New App Form

```
NAME:
VPS SSH Gateway

DESCRIPTION:
Remote MCP server for VPS management via SSH. Provides tools for command execution, file management, Docker operations, and system administration with safety safeguards.

MCP_SERVER_URL:
https://mcp.yourdomain.com/sse

AUTHENTICATION:
OAuth

OAUTH_NOTES:
- issuer: https://your-tenant.auth0.com/
- authorization_endpoint: https://your-tenant.auth0.com/authorize
- token_endpoint: https://your-tenant.auth0.com/oauth/token
- scopes: openid, profile, email, offline_access
- offline_access enabled: yes
```

### OAuth Configuration

1. In ChatGPT, select "OAuth" as authentication type
2. Enter your OAuth provider details
3. The MCP server will verify tokens on each request

## API Reference

### Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/sse` | GET | SSE endpoint for MCP protocol |
| `/message` | POST | Message endpoint for MCP over SSE |
| `/mcp` | POST | Direct MCP protocol endpoint |
| `/health` | GET | Health check |
| `/ready` | GET | Readiness check |
| `/auth/login` | GET | OAuth login initiation |
| `/auth/callback` | GET | OAuth callback |
| `/.well-known/openid-configuration` | GET | OIDC discovery |

### Health Check Response

```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "version": "1.0.0",
  "ssh": "connected",
  "oauth": "configured"
}
```

## Security

### Network Security
- SSH to experimental VPS restricted to Management VPS IP
- TLS 1.3 for all connections
- OAuth 2.0 authentication

### Application Security
- Rate limiting (100 req/min default)
- Dangerous command safeguards
- Comprehensive logging
- Secrets stored outside repository

### SSH Security
- Dedicated SSH key for MCP server
- Key-based authentication only
- No password authentication

## Troubleshooting

### Check service status
```bash
systemctl status mcp-server
journalctl -u mcp-server -f
```

### Check SSH connection
```bash
# Test SSH manually
sudo -u mcp ssh -i /opt/mcp-server/secrets/ssh_key root@<experimental-vps>
```

### Check OAuth
```bash
curl https://mcp.yourdomain.com/.well-known/openid-configuration
```

### Common Issues

1. **SSH Connection Failed**
   - Verify SSH key is added to experimental VPS
   - Check firewall allows SSH from management VPS IP
   - Verify SSH user has sudo privileges

2. **OAuth Token Invalid**
   - Verify OAuth configuration in `.env`
   - Check client ID and secret are correct
   - Ensure `offline_access` scope is enabled

3. **SSE Connection Drops**
   - Check nginx configuration for proxy timeouts
   - Verify TLS certificates are valid
   - Check rate limiting isn't blocking requests

## Development

### Local Development
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp config/.env.template .env
# Edit .env for local development
python -m mcp_server.main
```

### Running Tests
```bash
pytest tests/
```

## License

MIT License

## Support

For issues and feature requests, please open an issue on GitHub.
