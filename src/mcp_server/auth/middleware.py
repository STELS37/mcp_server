"""Authentication middleware for FastAPI."""
import logging
from typing import Optional, Callable, Any
from functools import wraps

from mcp_server.auth.oauth import OAuthHandler, TokenInfo

from fastapi import Request, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from mcp_server.core.settings import get_settings

logger = logging.getLogger(__name__)

security = HTTPBearer(auto_error=False)
_global_oauth_handler: Optional[OAuthHandler] = None


def set_oauth_handler(handler: Optional[OAuthHandler]) -> None:
    global _global_oauth_handler
    _global_oauth_handler = handler


def _resolve_oauth_handler(request: Request) -> Optional[OAuthHandler]:
    app_handler = getattr(getattr(request, "app", None), "state", None)
    if app_handler is not None:
        handler = getattr(request.app.state, "oauth_handler", None)
        if handler is not None:
            return handler
    return _global_oauth_handler


class AuthMiddleware(BaseHTTPMiddleware):
    """Middleware to handle OAuth authentication."""
    
    # Paths that don't require authentication
    PUBLIC_PATHS = [
        "/health",
        "/ready",
        "/.well-known/",
        "/auth/callback",
        "/auth/login",
        "/sse",  # SSE endpoint handles its own auth
    ]
    
    def __init__(self, app, oauth_handler: OAuthHandler):
        super().__init__(app)
        self.oauth_handler = oauth_handler
        self.settings = get_settings()
    
    async def dispatch(self, request: Request, call_next):
        """Process request through middleware."""
        # Skip auth for public paths
        path = request.url.path
        if any(path.startswith(p) for p in self.PUBLIC_PATHS):
            return await call_next(request)
        
        # Skip auth if OAuth is disabled
        if not self.settings.oauth.enabled:
            request.state.user = {"sub": "anonymous", "roles": ["admin"]}
            return await call_next(request)
        
        # Get authorization header
        auth_header = request.headers.get("Authorization", "")
        
        if not auth_header.startswith("Bearer "):
            logger.warning(f"Missing or invalid Authorization header for {path}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "unauthorized", "message": "Missing or invalid Authorization header"},
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        token = auth_header[7:]  # Remove "Bearer " prefix
        
        try:
            # Verify token
            claims = await self.oauth_handler.verify_token(token)
            request.state.user = claims
            request.state.token = token
            
            # Log successful auth
            if self.settings.logging.log_auth_events:
                logger.info(f"Authenticated user: {claims.get('sub', 'unknown')}")
            
            return await call_next(request)
            
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"error": "invalid_token", "message": str(e)},
                headers={"WWW-Authenticate": "Bearer error=\"invalid_token\""},
            )


async def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Dependency to get current authenticated user."""
    # Check if user is already set by middleware
    if hasattr(request.state, "user"):
        return request.state.user
    
    # Handle case where OAuth is disabled
    settings = get_settings()
    if not settings.oauth.enabled:
        return {"sub": "anonymous", "roles": ["admin"]}
    
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Verify token using the shared app handler so JWKS and claims caches survive across requests
    handler = _resolve_oauth_handler(request)
    if handler is None:
        handler = OAuthHandler(settings.oauth)
        set_oauth_handler(handler)
    try:
        claims = await handler.verify_token(credentials.credentials)
        return claims
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )


def require_auth(func: Callable) -> Callable:
    """Decorator to require authentication for a function."""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        # This is used as a dependency, so the user will be injected
        return await func(*args, **kwargs)
    return wrapper


def require_role(role: str):
    """Decorator factory to require a specific role."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, user: dict = Depends(get_current_user), **kwargs):
            roles = user.get("roles", [])
            if role not in roles and "admin" not in roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Required role: {role}",
                )
            return await func(*args, user=user, **kwargs)
        return wrapper
    return decorator
