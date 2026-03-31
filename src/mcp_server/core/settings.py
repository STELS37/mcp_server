"""Configuration settings with environment variable support."""
import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class ServerSettings(BaseSettings):
    """Server configuration."""
    model_config = SettingsConfigDict(env_prefix="MCP_SERVER__")
    
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    log_level: str = "info"
    cors_origins: List[str] = Field(
        default=[
            "https://chat.openai.com",
            "https://chatgpt.com",
            "https://cdn.oaistatic.com",
            "https://cdn.auth0.com",
        ]
    )


class MCPCapabilitiesSettings(BaseSettings):
    """MCP protocol capabilities."""
    model_config = SettingsConfigDict(env_prefix="MCP_CAPABILITIES__")
    
    tools: bool = True
    resources: bool = False
    prompts: bool = False
    logging: bool = True


class MCPSettings(BaseSettings):
    """MCP protocol configuration."""
    model_config = SettingsConfigDict(env_prefix="MCP__")
    
    server_name: str = "VPS SSH Gateway"
    server_version: str = "1.0.0"
    protocol_version: str = "2024-11-05"
    capabilities: MCPCapabilitiesSettings = Field(default_factory=MCPCapabilitiesSettings)

class RouterSettings(BaseSettings):
    """Router mode configuration - control legacy vs new tool system."""
    model_config = SettingsConfigDict(env_prefix="MCP_ROUTER__", extra="ignore")
    
    # Enable universal action router (execute_server_action)
    enabled: bool = True
    # Disable legacy individual tools when True
    disable_legacy_tools: bool = True
    # Router phase: "read_only" | "controlled_mutation" | "full"
    phase: str = "full"
    # Preview mode enabled
    preview_enabled: bool = True
    # Allow shell/bash commands through router
    allow_shell_actions: bool = True
    # Allow mutation actions (restart, write, etc.)
    allow_mutation_actions: bool = True



class SSHSettings(BaseSettings):
    """SSH connection configuration."""
    model_config = SettingsConfigDict(env_prefix="MCP_SSH__")
    
    host: str = Field(default="", description="Target VPS hostname or IP")
    port: int = 22
    user: str = Field(default="", description="SSH username")
    private_key_path: str = Field(
        default="/app/secrets/ssh_key",
        description="Path to SSH private key file"
    )
    private_key_passphrase: Optional[str] = Field(
        default=None,
        description="Passphrase for encrypted private key"
    )
    connection_timeout: int = 30
    command_timeout: int = 30
    max_output_size: int = 65536  # 64 KB
    max_sessions: int = 10
    keepalive_interval: int = 30
    sudo_enabled: bool = True
    sudo_password: Optional[str] = Field(
        default=None,
        description="Password for sudo (if required)"
    )
    
    @field_validator("host", "user")
    @classmethod
    def validate_required(cls, v: str) -> str:
        if not v:
            raise ValueError("SSH host and user must be configured")
        return v


class OAuthSettings(BaseSettings):
    """OAuth/OIDC configuration."""
    model_config = SettingsConfigDict(env_prefix="MCP_OAUTH__")
    
    enabled: bool = True
    issuer_url: str = Field(default="", description="OAuth issuer URL")
    authorization_endpoint: str = Field(default="", description="Authorization endpoint URL")
    token_endpoint: str = Field(default="", description="Token endpoint URL")
    userinfo_endpoint: Optional[str] = Field(default=None, description="Userinfo endpoint URL")
    jwks_uri: str = Field(default="", description="JWKS URI for key verification")
    client_id: str = Field(default="", description="OAuth client ID")
    client_secret: str = Field(default="", description="OAuth client secret")
    scopes: List[str] = Field(
        default=["openid", "profile", "email", "offline_access"]
    )
    audience: Optional[str] = Field(default=None, description="API audience")
    redirect_uris: List[str] = Field(default_factory=list)
    refresh_token_enabled: bool = True
    token_expiry_leeway: int = 60


    @field_validator("scopes", mode="before")
    @classmethod
    def normalize_scopes(cls, v):
        if isinstance(v, list):
            return v
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith('['):
                import json
                try:
                    arr = json.loads(s)
                    if isinstance(arr, list):
                        return [str(x).strip() for x in arr if str(x).strip()]
                except Exception:
                    s2 = s.strip('[]')
                    return [x.strip().strip("\"'") for x in s2.split(",") if x.strip()]
            return [x.strip() for x in s.split(',') if x.strip()]
        return v


class SecuritySettings(BaseSettings):
    """Security configuration."""
    model_config = SettingsConfigDict(env_prefix="MCP_SECURITY__")
    
    rate_limit_requests: int = 100
    rate_limit_period: int = 60
    dangerous_commands: List[str] = Field(
        default=[
            "reboot", "shutdown", "init", "halt", "poweroff",
            "rm", "rmdir", "dd", "mkfs", "fdisk", "parted",
            "ufw", "iptables", "ip6tables", "firewall-cmd",
            "userdel", "useradd", "usermod", "passwd", "chage",
            "groupdel", "groupadd", "visudo",
            "systemctl", "journalctl", "docker", "kubectl",
        ]
    )
    dangerous_patterns: List[str] = Field(
        default=[
            "rm -rf", "rm -r", "rm -R", "rm /*", "> /dev/", 
            "dd if=", ":(){ :|:& };:",
        ]
    )
    require_confirm_params: List[str] = Field(
        default=["confirm", "force", "yes"]
    )
    enforce_confirmations: bool = False


class LoggingSettings(BaseSettings):
    """Logging configuration."""
    model_config = SettingsConfigDict(env_prefix="MCP_LOGGING__")
    
    level: str = "INFO"
    format: str = "json"
    path: str = "/var/log/mcp-server"
    max_size: int = 10485760  # 10 MB
    backup_count: int = 5
    log_tool_calls: bool = True
    log_auth_events: bool = True
    log_ssh_sessions: bool = True


class HealthSettings(BaseSettings):
    """Health check configuration."""
    model_config = SettingsConfigDict(env_prefix="MCP_HEALTH__")
    
    enabled: bool = True
    path: str = "/health"
    readiness_path: str = "/ready"
    ssh_check: bool = True
    oauth_check: bool = True


class Settings(BaseSettings):
    """Main application settings."""
    model_config = SettingsConfigDict(
        env_prefix="MCP_",
        env_nested_delimiter="__",
        case_sensitive=False,
        extra="ignore",
        env_file=("/a0/usr/projects/mcp_server/.runtime/mcp_stable.env",),
        env_file_encoding="utf-8",
    )
    
    # Base URL for the MCP server (used for OAuth redirect)
    base_url: str = Field(
        default="http://localhost:8000",
        description="Base URL of the MCP server"
    )
    
    # Environment
    environment: str = "production"
    debug: bool = False
    test_mode: bool = False
    disable_confirm: bool = False
    # Sub-settings
    server: ServerSettings = Field(default_factory=ServerSettings)
    mcp: MCPSettings = Field(default_factory=MCPSettings)
    ssh: SSHSettings = Field(default_factory=SSHSettings)
    oauth: OAuthSettings = Field(default_factory=OAuthSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    health: HealthSettings = Field(default_factory=HealthSettings)
    router: RouterSettings = Field(default_factory=RouterSettings)
    
    # Redis for rate limiting (optional)
    redis_url: Optional[str] = Field(
        default=None,
        description="Redis URL for rate limiting and session storage"
    )
    
    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        if not v:
            raise ValueError("MCP_BASE_URL must be configured")
        return v.rstrip("/")


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create settings instance."""
    global _settings
    if _settings is None:
        try:
            _settings = Settings()
        except Exception:
            env_path = "/a0/usr/projects/mcp_server/.runtime/mcp_stable.env"
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for raw in f:
                        line = raw.strip()
                        if not line or line.startswith("#") or "=" not in line:
                            continue
                        k, v = line.split("=", 1)
                        k = k.strip(); v = v.strip()
                        if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                            v = v[1:-1]
                        os.environ.setdefault(k, v)
            except Exception:
                pass
            _settings = Settings()
    return _settings


def reload_settings() -> Settings:
    """Force reload settings from environment."""
    global _settings
    _settings = Settings()
    return _settings

