"""Main FastAPI Application for MCP SSH Gateway."""
import logging
import asyncio
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
import structlog

from mcp_server.core.settings import get_settings
from mcp_server.auth.oauth import OAuthHandler
from mcp_server.auth.middleware import AuthMiddleware
from mcp_server.tools.ssh_client import SSHClient
from mcp_server.tools.mcp_tools import MCPTools
from mcp_server.api.sse_transport import SSETransport, MCPProtocolHandler
from mcp_server.api.routes import (
    router, auth_router, health_router,
    set_app_instances
)

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    wrapper_class=structlog.stdlib.BoundLogger,
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Global instances
_ssh_client: Optional[SSHClient] = None
_tools: Optional[MCPTools] = None
_oauth_handler: Optional[OAuthHandler] = None
_sse_transport: Optional[SSETransport] = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    settings = get_settings()
    
    logger.info("Starting MCP SSH Gateway", version=settings.mcp.server_version)
    
    # Initialize SSH client
    global _ssh_client, _tools, _oauth_handler, _sse_transport
    
    try:
        _ssh_client = SSHClient(settings.ssh)
        
        # Connect to SSH (with retry logic in production)
        if settings.health.ssh_check:
            try:
                await _ssh_client.connect()
                logger.info("SSH connection established", host=settings.ssh.host)
            except Exception as e:
                logger.warning(f"SSH connection failed (will retry on demand): {e}")
        
        # Initialize tools
        _tools = MCPTools(_ssh_client)
        logger.info("MCP tools initialized", tool_count=len(_tools._tools))
        
    except Exception as e:
        logger.error(f"Failed to initialize SSH client: {e}")
    
    # Initialize OAuth handler
    if settings.oauth.enabled:
        try:
            _oauth_handler = OAuthHandler(settings.oauth)
            logger.info("OAuth handler initialized", issuer=settings.oauth.issuer_url)
        except Exception as e:
            logger.error(f"Failed to initialize OAuth handler: {e}")
    
    # Initialize SSE transport
    protocol_handler = MCPProtocolHandler(_ssh_client, _tools, _oauth_handler)
    _sse_transport = SSETransport(protocol_handler)
    logger.info("SSE transport initialized")
    
    # Set global instances for routes
    set_app_instances(_ssh_client, _tools, _oauth_handler, _sse_transport)
    
    yield
    
    # Cleanup
    logger.info("Shutting down MCP SSH Gateway")
    
    if _ssh_client:
        await _ssh_client.disconnect()
    
    if _oauth_handler:
        await _oauth_handler.close()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()
    
    app = FastAPI(
        title=settings.mcp.server_name,
        description="Remote MCP Server for ChatGPT with SSH Gateway to VPS",
        version=settings.mcp.server_version,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )
    
    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.server.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=[
            "Authorization",
            "Content-Type",
            "Accept",
            "Cache-Control",
            "X-Request-ID",
        ],
    )
    
    # Auth middleware (for non-public routes)
    # Note: We apply this selectively, as SSE endpoint handles its own auth
    # app.add_middleware(AuthMiddleware, oauth_handler=_oauth_handler)
    
    # Rate limiting
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    
    # Include routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(router)
    
    # Root endpoint
    @app.get("/")
    async def root():
        """Root endpoint with basic info."""
        return {
            "name": settings.mcp.server_name,
            "version": settings.mcp.server_version,
            "protocol": "MCP over SSE",
            "sse_endpoint": f"{settings.base_url}/sse",
            "docs": f"{settings.base_url}/docs",
        }
    
    # Global exception handler
    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {exc}", exc_info=True)
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": str(exc),
            }
        )
    
    return app


def run_server():
    """Run the server using uvicorn."""
    import uvicorn
    
    settings = get_settings()
    
    uvicorn.run(
        "mcp_server.main:app",
        host=settings.server.host,
        port=settings.server.port,
        workers=settings.server.workers,
        log_level=settings.server.log_level,
        reload=settings.debug,
    )


# Create app instance for uvicorn
app = create_app()


if __name__ == "__main__":
    run_server()
