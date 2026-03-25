"""OAuth/OIDC Authentication Handler with refresh token support."""
import time
import httpx
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import json
import base64

from jose import jwt, jwk, JWTError
from jose.utils import base64url_decode

from mcp_server.core.settings import get_settings, OAuthSettings

logger = logging.getLogger(__name__)


@dataclass
class TokenInfo:
    """Token information with refresh support."""
    access_token: str
    token_type: str = "Bearer"
    expires_at: Optional[float] = None
    refresh_token: Optional[str] = None
    id_token: Optional[str] = None
    scope: Optional[str] = None
    user_info: Optional[Dict[str, Any]] = None
    
    @property
    def is_expired(self) -> bool:
        if not self.expires_at:
            return False
        # Add leeway for clock skew
        leeway = get_settings().oauth.token_expiry_leeway
        return time.time() > (self.expires_at - leeway)
    
    @property
    def needs_refresh(self) -> bool:
        if not self.refresh_token:
            return False
        if not self.expires_at:
            return False
        # Refresh when we're at 80% of token lifetime
        refresh_threshold = self.expires_at - (self.expires_at - time.time()) * 0.2
        return time.time() > refresh_threshold


class OAuthHandler:
    """OAuth/OIDC handler with refresh token support."""
    
    def __init__(self, settings: Optional[OAuthSettings] = None):
        self.settings = settings or get_settings().oauth
        self._jwks_cache: Dict[str, Any] = {}
        self._jwks_last_fetch: float = 0
        self._jwks_cache_ttl: int = 3600  # 1 hour
        self._http_client = httpx.AsyncClient(timeout=30.0)
        self._token_storage: Dict[str, TokenInfo] = {}  # session_id -> TokenInfo
        
    async def close(self):
        """Close HTTP client."""
        await self._http_client.aclose()
    
    @property
    def authorization_url(self) -> str:
        """Get the authorization endpoint URL."""
        return self.settings.authorization_endpoint
    
    @property
    def token_url(self) -> str:
        """Get the token endpoint URL."""
        return self.settings.token_endpoint
    
    @property
    def userinfo_url(self) -> Optional[str]:
        """Get the userinfo endpoint URL."""
        return self.settings.userinfo_endpoint
    
    def get_authorization_url(self, state: str, redirect_uri: str, scope: Optional[str] = None) -> str:
        """Generate authorization URL for OAuth flow."""
        params = {
            "client_id": self.settings.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "state": state,
            "scope": scope or " ".join(self.settings.scopes),
        }
        
        # Add offline_access for refresh tokens
        if self.settings.refresh_token_enabled and "offline_access" not in params["scope"]:
            params["scope"] += " offline_access"
        
        # Add audience if specified
        if self.settings.audience:
            params["audience"] = self.settings.audience
        
        query = "&".join(f"{k}={v}" for k, v in params.items())
        return f"{self.settings.authorization_endpoint}?{query}"
    
    async def exchange_code_for_token(
        self,
        code: str,
        redirect_uri: str,
    ) -> TokenInfo:
        """Exchange authorization code for access token."""
        data = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": redirect_uri,
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        
        response = await self._http_client.post(
            self.settings.token_endpoint,
            data=data,
            headers=headers,
        )
        response.raise_for_status()
        
        token_data = response.json()
        return self._parse_token_response(token_data)
    
    async def refresh_access_token(self, refresh_token: str) -> TokenInfo:
        """Refresh access token using refresh token."""
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
            "Accept": "application/json",
        }
        
        response = await self._http_client.post(
            self.settings.token_endpoint,
            data=data,
            headers=headers,
        )
        response.raise_for_status()
        
        token_data = response.json()
        return self._parse_token_response(token_data)
    
    def _parse_token_response(self, data: Dict[str, Any]) -> TokenInfo:
        """Parse token response into TokenInfo."""
        expires_at = None
        if "expires_in" in data:
            expires_at = time.time() + data["expires_in"]
        
        return TokenInfo(
            access_token=data["access_token"],
            token_type=data.get("token_type", "Bearer"),
            expires_at=expires_at,
            refresh_token=data.get("refresh_token"),
            id_token=data.get("id_token"),
            scope=data.get("scope"),
        )
    
    async def get_user_info(self, access_token: str) -> Dict[str, Any]:
        """Get user info from userinfo endpoint."""
        if not self.settings.userinfo_endpoint:
            # Decode ID token if available
            return {}
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json",
        }
        
        response = await self._http_client.get(
            self.settings.userinfo_endpoint,
            headers=headers,
        )
        response.raise_for_status()
        
        return response.json()
    
    async def verify_token(self, token: str) -> Dict[str, Any]:
        """Verify JWT access token and return claims."""
        try:
            # Decode header to get key ID
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            
            if not kid:
                raise ValueError("Token missing key ID (kid)")
            
            # Get signing key
            signing_key = await self._get_signing_key(kid)
            
            # Verify and decode token
            payload = jwt.decode(
                token,
                signing_key,
                algorithms=["RS256", "RS384", "RS512", "ES256", "ES384", "ES512"],
                audience=self.settings.client_id,
                issuer=self.settings.issuer_url,
            )
            
            return payload
            
        except JWTError as e:
            logger.error(f"JWT verification failed: {e}")
            raise ValueError(f"Invalid token: {e}")
    
    async def _get_signing_key(self, kid: str) -> str:
        """Get signing key from JWKS."""
        # Check cache
        now = time.time()
        if kid in self._jwks_cache and (now - self._jwks_last_fetch) < self._jwks_cache_ttl:
            return self._jwks_cache[kid]
        
        # Fetch JWKS
        jwks_data = await self._fetch_jwks()
        
        for key in jwks_data.get("keys", []):
            key_kid = key.get("kid")
            if key_kid:
                # Convert JWK to PEM format
                self._jwks_cache[key_kid] = jwk.construct(key).public_key()
        
        self._jwks_last_fetch = now
        
        if kid not in self._jwks_cache:
            raise ValueError(f"No matching key found for kid: {kid}")
        
        return self._jwks_cache[kid]
    
    async def _fetch_jwks(self) -> Dict[str, Any]:
        """Fetch JWKS from the configured URI."""
        response = await self._http_client.get(self.settings.jwks_uri)
        response.raise_for_status()
        return response.json()
    
    def get_oidc_metadata(self) -> Dict[str, Any]:
        """Get OIDC discovery metadata."""
        return {
            "issuer": self.settings.issuer_url,
            "authorization_endpoint": self.settings.authorization_endpoint,
            "token_endpoint": self.settings.token_endpoint,
            "userinfo_endpoint": self.settings.userinfo_endpoint,
            "jwks_uri": self.settings.jwks_uri,
            "scopes_supported": self.settings.scopes,
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "token_endpoint_auth_methods_supported": ["client_secret_basic", "client_secret_post"],
            "refresh_token_enabled": self.settings.refresh_token_enabled,
        }
    
    def store_token(self, session_id: str, token_info: TokenInfo) -> None:
        """Store token info for a session."""
        self._token_storage[session_id] = token_info
    
    def get_token(self, session_id: str) -> Optional[TokenInfo]:
        """Get token info for a session."""
        return self._token_storage.get(session_id)
    
    def remove_token(self, session_id: str) -> None:
        """Remove token for a session."""
        self._token_storage.pop(session_id, None)
