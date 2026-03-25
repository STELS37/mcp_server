"""API Routes for MCP Server."""
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Request, Response, HTTPException, Depends, Query
from fastapi.responses import JSONResponse, RedirectResponse
from sse_starlette.sse import EventSourceResponse
import structlog

from mcp_server.core.settings import get_settings
from mcp_server.auth.oauth import OAuthHandler
from mcp_server.auth.middleware import get_current_user
from mcp_server.api.sse_transport import SSETransport, MCPProtocolHandler
from mcp_server.tools.ssh_client import SSHClient
from mcp_server.tools.mcp_tools import MCPTools

logger = structlog.get_logger()

# Create routers
router = APIRouter()
auth_router = APIRouter(prefix="/auth", tags=["Authentication"])
health_router = APIRouter(tags=["Health"])


# Global instances (set by main app)
_ssh_client: Optional[SSHClient] = None
_tools: Optional[MCPTools] = None
_oauth_handler: Optional[OAuthHandler] = None
_sse_transport: Optional[SSETransport] = None


def set_app_instances(
    ssh_client: SSHClient,
    tools: MCPTools,
    oauth_handler: Optional[OAuthHandler],
    sse_transport: SSETransport,
):
    """Set global instances for the application."""
    global _ssh_client, _tools, _oauth_handler, _sse_transport
    _ssh_client = ssh_client
    _tools = tools
    _oauth_handler = oauth_handler
    _sse_transport = sse_transport


# Health endpoints
@health_router.get("/health")
async def health_check():
    """Health check endpoint."""
    settings = get_settings()
    
    health_status = {
        "status": "healthy",
        "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
        "version": settings.mcp.server_version,
    }
    
    # Check SSH if enabled
    if settings.health.ssh_check and _ssh_client:
        health_status["ssh"] = "connected" if _ssh_client.is_connected else "disconnected"
    
    # Check OAuth if enabled
    if settings.health.oauth_check and settings.oauth.enabled:
        health_status["oauth"] = "configured" if settings.oauth.client_id else "not_configured"
    
    return JSONResponse(health_status)


@health_router.get("/ready")
async def readiness_check():
    """Readiness check endpoint."""
    settings = get_settings()
    
    checks = {}
    ready = True
    
    # Check SSH connection
    if _ssh_client:
        if _ssh_client.is_connected:
            checks["ssh"] = "ready"
        else:
            # Try to connect
            try:
                await _ssh_client.connect()
                checks["ssh"] = "ready"
            except Exception as e:
                checks["ssh"] = f"not_ready: {str(e)}"
                ready = False
    else:
        checks["ssh"] = "not_initialized"
        ready = False
    
    # Check OAuth configuration
    if settings.oauth.enabled:
        required_oauth = [
            settings.oauth.issuer_url,
            settings.oauth.client_id,
            settings.oauth.client_secret,
        ]
        if all(required_oauth):
            checks["oauth"] = "configured"
        else:
            checks["oauth"] = "incomplete"
            ready = False
    else:
        checks["oauth"] = "disabled"
    
    status_code = 200 if ready else 503
    return JSONResponse(
        {
            "ready": ready,
            "checks": checks,
            "timestamp": __import__('datetime').datetime.utcnow().isoformat(),
        },
        status_code=status_code
    )


# Auth endpoints
@auth_router.get("/login")
async def login(redirect_uri: Optional[str] = None):
    """Initiate OAuth login flow."""
    if not _oauth_handler:
        raise HTTPException(status_code=501, detail="OAuth not configured")
    
    settings = get_settings()
    state = str(uuid.uuid4())
    
    # Use provided redirect_uri or default
    callback_uri = f"{settings.base_url}/auth/callback"
    if redirect_uri:
        # Store the final redirect target
        # In production, use secure session storage
        pass
    
    auth_url = _oauth_handler.get_authorization_url(state, callback_uri)
    
    return RedirectResponse(url=auth_url)


@auth_router.get("/callback")
async def callback(code: str = Query(...), state: str = Query(...)):
    """OAuth callback endpoint."""
    if not _oauth_handler:
        raise HTTPException(status_code=501, detail="OAuth not configured")
    
    settings = get_settings()
    callback_uri = f"{settings.base_url}/auth/callback"
    
    try:
        # Exchange code for token
        token_info = await _oauth_handler.exchange_code_for_token(code, callback_uri)
        
        # Get user info
        user_info = await _oauth_handler.get_user_info(token_info.access_token)
        token_info.user_info = user_info
        
        # Store token
        session_id = str(uuid.uuid4())
        _oauth_handler.store_token(session_id, token_info)
        
        # Return session info
        return JSONResponse({
            "status": "success",
            "session_id": session_id,
            "user": user_info,
            "token_type": token_info.token_type,
            "expires_in": int(token_info.expires_at - __import__('time').time()) if token_info.expires_at else None,
            "refresh_token_available": token_info.refresh_token is not None,
        })
        
    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@auth_router.post("/refresh")
async def refresh_token(refresh_token: str):
    """Refresh access token."""
    if not _oauth_handler:
        raise HTTPException(status_code=501, detail="OAuth not configured")
    
    try:
        token_info = await _oauth_handler.refresh_access_token(refresh_token)
        
        return JSONResponse({
            "access_token": token_info.access_token,
            "token_type": token_info.token_type,
            "expires_in": int(token_info.expires_at - __import__('time').time()) if token_info.expires_at else None,
            "refresh_token": token_info.refresh_token,
        })
        
    except Exception as e:
        logger.error(f"Token refresh error: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@auth_router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    """OAuth authorization server metadata."""
    if not _oauth_handler:
        raise HTTPException(status_code=501, detail="OAuth not configured")
    
    return JSONResponse(_oauth_handler.get_oidc_metadata())


# MCP SSE endpoint - main entry point for ChatGPT
@router.get("/sse")
async def sse_endpoint(
    request: Request,
    session_id: Optional[str] = Query(None),
    user: dict = Depends(get_current_user),
):
    """SSE endpoint for MCP protocol."""
    if not _sse_transport:
        raise HTTPException(status_code=501, detail="SSE transport not initialized")
    
    username = user.get("sub", "unknown") if user else "unknown"
    
    return await _sse_transport.handle_sse_connection(
        request=request,
        session_id=session_id,
        user=username,
    )


@router.post("/message")
async def message_endpoint(
    request: Request,
    session_id: str = Query(...),
    user: dict = Depends(get_current_user),
):
    """Message endpoint for MCP over SSE."""
    if not _sse_transport:
        raise HTTPException(status_code=501, detail="SSE transport not initialized")
    
    username = user.get("sub", "unknown") if user else "unknown"
    
    response = await _sse_transport.handle_message(
        request=request,
        session_id=session_id,
        user=username,
    )
    
    return JSONResponse(response)


# OIDC Discovery
@router.get("/.well-known/openid-configuration")
async def openid_configuration():
    """OpenID Connect discovery endpoint."""
    settings = get_settings()
    
    if not settings.oauth.enabled:
        raise HTTPException(status_code=404, detail="OpenID Connect not enabled")
    
    return JSONResponse({
        "issuer": settings.oauth.issuer_url,
        "authorization_endpoint": settings.oauth.authorization_endpoint,
        "token_endpoint": settings.oauth.token_endpoint,
        "userinfo_endpoint": settings.oauth.userinfo_endpoint,
        "jwks_uri": settings.oauth.jwks_uri,
        "scopes_supported": settings.oauth.scopes,
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
        "code_challenge_methods_supported": ["S256"],
    })


# MCP Protocol endpoint (alternative to SSE for some clients)
@router.post("/mcp")
async def mcp_endpoint(
    request: Request,
    user: dict = Depends(get_current_user),
):
    """Direct MCP protocol endpoint (for clients that don't use SSE)."""
    if not _tools:
        raise HTTPException(status_code=501, detail="MCP tools not initialized")
    
    try:
        body = await request.json()
        
        protocol = MCPProtocolHandler(_ssh_client, _tools, _oauth_handler)
        username = user.get("sub", "unknown") if user else "unknown"
        session_id = str(uuid.uuid4())
        
        response = await protocol.process_message(body, session_id, username)
        
        return JSONResponse(response)
        
    except json.JSONDecodeError:
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            },
            status_code=400
        )
    except Exception as e:
        logger.error(f"MCP endpoint error: {e}")
        return JSONResponse(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            },
            status_code=500
        )
