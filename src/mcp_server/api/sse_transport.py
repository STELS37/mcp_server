"""SSE Transport for MCP Protocol - ChatGPT Compatible."""
import json
import logging
import asyncio
import uuid
from typing import Optional, Dict, Any, AsyncGenerator
from datetime import datetime

from fastapi import Request, Query
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import structlog

from mcp_server.core.settings import get_settings
from mcp_server.auth.oauth import OAuthHandler
from mcp_server.tools.mcp_tools import MCPTools
from mcp_server.tools.ssh_client import SSHClient

logger = structlog.get_logger()


class MCPProtocolHandler:
    """Handler for MCP protocol messages over SSE."""
    
    # MCP Protocol Version
    PROTOCOL_VERSION = "2024-11-05"
    
    def __init__(
        self,
        ssh_client: SSHClient,
        tools: MCPTools,
        oauth_handler: Optional[OAuthHandler] = None,
    ):
        self.ssh = ssh_client
        self.tools = tools
        self.oauth = oauth_handler
        self.settings = get_settings()
        self._sessions: Dict[str, Dict[str, Any]] = {}
    
    def _get_server_info(self) -> Dict[str, Any]:
        """Get server information."""
        return {
            "name": self.settings.mcp.server_name,
            "version": self.settings.mcp.server_version,
        }
    
    def _get_capabilities(self) -> Dict[str, Any]:
        """Get server capabilities."""
        return {
            "protocolVersion": self.PROTOCOL_VERSION,
            "capabilities": {
                "tools": {},
                "logging": {},
            },
            "serverInfo": self._get_server_info(),
        }
    
    async def handle_initialize(self, params: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Handle initialize request."""
        # Store client info
        self._sessions[session_id] = {
            "client_info": params.get("clientInfo", {}),
            "protocol_version": params.get("protocolVersion", self.PROTOCOL_VERSION),
            "capabilities": params.get("capabilities", {}),
            "initialized": True,
        }
        
        logger.info(f"Session {session_id} initialized", client_info=params.get("clientInfo"))
        
        return self._get_capabilities()
    
    async def handle_list_tools(self, params: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Handle tools/list request."""
        return {
            "tools": self.tools.get_tool_definitions()
        }
    
    async def handle_call_tool(self, params: Dict[str, Any], session_id: str, user: str = "unknown") -> Dict[str, Any]:
        """Handle tools/call request."""
        tool_name = params.get("name")
        arguments = params.get("arguments", {})
        
        if not tool_name:
            return {
                "isError": True,
                "content": [{
                    "type": "text",
                    "text": "Missing tool name"
                }]
            }
        
        logger.info(f"Tool call: {tool_name}", arguments=arguments, user=user, session=session_id)
        
        result = await self.tools.execute_tool(tool_name, arguments, user)
        
        return result
    
    async def handle_ping(self, params: Dict[str, Any], session_id: str) -> Dict[str, Any]:
        """Handle ping request."""
        return {}
    
    async def process_message(
        self,
        message: Dict[str, Any],
        session_id: str,
        user: str = "unknown"
    ) -> Dict[str, Any]:
        """Process a single MCP message."""
        method = message.get("method", "")
        params = message.get("params", {})
        request_id = message.get("id")
        
        handlers = {
            "initialize": self.handle_initialize,
            "tools/list": self.handle_list_tools,
            "tools/call": self.handle_call_tool,
            "ping": self.handle_ping,
        }
        
        handler = handlers.get(method)
        
        if not handler:
            # Check for notifications (no response needed)
            if method.startswith("notifications/"):
                logger.debug(f"Received notification: {method}")
                return None
            
            # Unknown method
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }
        
        try:
            if method == "tools/call":
                result = await handler(params, session_id, user)
            else:
                result = await handler(params, session_id)
            
            # Return response
            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": result
            }
            return response
            
        except Exception as e:
            logger.error(f"Error handling {method}: {e}")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": str(e)
                }
            }


class SSETransport:
    """SSE Transport for MCP over HTTP."""
    
    def __init__(self, protocol_handler: MCPProtocolHandler):
        self.protocol = protocol_handler
        self.settings = get_settings()
        self._pending_requests: Dict[str, asyncio.Future] = {}
    
    async def handle_sse_connection(
        self,
        request: Request,
        session_id: Optional[str] = None,
        user: str = "unknown",
    ) -> EventSourceResponse:
        """Handle SSE connection from ChatGPT."""
        
        async def event_generator() -> AsyncGenerator[Dict[str, Any], None]:
            """Generate SSE events."""
            # Generate session ID if not provided
            sid = session_id or str(uuid.uuid4())
            
            # Send endpoint event (for HTTP+SSE transport)
            yield {
                "event": "endpoint",
                "data": f"{self.settings.base_url}/message?session_id={sid}"
            }
            
            # Keep connection alive
            try:
                while True:
                    # Check for disconnect
                    if await request.is_disconnected():
                        logger.info(f"SSE client disconnected: {sid}")
                        break
                    
                    # Send keepalive
                    await asyncio.sleep(30)
                    yield {
                        "event": "keepalive",
                        "data": ""
                    }
                    
            except asyncio.CancelledError:
                logger.info(f"SSE connection cancelled: {sid}")
            except Exception as e:
                logger.error(f"SSE error: {e}")
        
        return EventSourceResponse(event_generator())
    
    async def handle_message(
        self,
        request: Request,
        session_id: str,
        user: str = "unknown",
    ) -> Dict[str, Any]:
        """Handle incoming message via POST."""
        try:
            body = await request.json()
            
            # Process the message
            response = await self.protocol.process_message(body, session_id, user)
            
            return response
            
        except json.JSONDecodeError:
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                }
            }
        except Exception as e:
            logger.error(f"Message handling error: {e}")
            return {
                "jsonrpc": "2.0",
                "id": None,
                "error": {
                    "code": -32603,
                    "message": "Internal error"
                }
            }
