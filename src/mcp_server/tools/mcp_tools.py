"""MCP Tools - Router architecture with extra tools support."""
import inspect
import logging
import json
from typing import Dict, Any, Callable, Optional, List
from dataclasses import dataclass
from pathlib import Path

# Import single router tool
from mcp_server.tools.single_router_tool import register_single_router_tool

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """MCP Tool definition."""
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable
    dangerous: bool = False
    annotations: Optional[Dict[str, Any]] = None


class MCPTools:
    """MCP Tools - Router architecture with workflow support."""
    
    def __init__(self, ssh_client=None):
        self.ssh = ssh_client
        self._tools: Dict[str, ToolDefinition] = {}
        self._action_history: List[Dict[str, Any]] = []
        self.extra_tools: Dict[str, Dict[str, Any]] = {}
        
        # Register single router tool first
        count = register_single_router_tool(self)
        logger.info(f"Registered {count} tool (system_status)")
        
        # Register extra tools (workflow, orchestrator, etc.)
        self._register_extra_tools()
        
        # Convert dict to ToolDefinition
        self._convert_dict_to_tooldef()
        
        # Merge extra tools
        self._merge_extra_tools()
    
    def _register_tool(self, name_or_tool, description: str = None, input_schema: Dict[str, Any] = None,
                       handler: Callable = None, dangerous: bool = False,
                       annotations: Optional[Dict[str, Any]] = None) -> None:
        """Register a tool. Accepts either positional args or a tool object."""
        # Support passing a tool object (ExtraToolDefinition, dict, etc.)
        if hasattr(name_or_tool, 'name'):
            # It's a tool object like ExtraToolDefinition
            tool = name_or_tool
            self._tools[tool.name] = ToolDefinition(
                name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                handler=tool.handler,
                dangerous=getattr(tool, 'dangerous', False),
                annotations=getattr(tool, 'annotations', None) or {}
            )
            logger.info(f"Registered tool: {tool.name}")
        elif isinstance(name_or_tool, dict):
            # It's a dict
            tool_data = name_or_tool
            name = tool_data.get('name', 'unknown')
            self._tools[name] = ToolDefinition(
                name=name,
                description=tool_data.get('description', ''),
                input_schema=tool_data.get('input_schema', {}),
                handler=tool_data['handler'],
                dangerous=tool_data.get('dangerous', False),
                annotations=tool_data.get('annotations', {})
            )
            logger.info(f"Registered tool: {name}")
        else:
            # Positional args
            self._tools[name_or_tool] = ToolDefinition(
                name=name_or_tool,
                description=description or '',
                input_schema=input_schema or {},
                handler=handler,
                dangerous=dangerous,
                annotations=annotations or {}
            )
            logger.info(f"Registered tool: {name_or_tool}")
    
    def _register_extra_tools(self) -> None:
        """Register workflow, orchestrator, router, and playbook tools."""
        # Workflow tools
        try:
            from mcp_server.tools.workflow_tools import register_workflow_tools
            register_workflow_tools(self)
            logger.info("Workflow tools registered")
        except ImportError as e:
            logger.warning(f"Workflow tools not available: {e}")
        
        # Router tools
        try:
            from mcp_server.tools.router_tools import register_router_tools
            register_router_tools(self)
            logger.info("Router tools registered")
        except ImportError as e:
            logger.warning(f"Router tools not available: {e}")
        
        # Orchestrator tools
        try:
            from mcp_server.tools.orchestrator_tools import register_orchestrator_tools
            register_orchestrator_tools(self)
            logger.info("Orchestrator tools registered")
        except ImportError as e:
            logger.warning(f"Orchestrator tools not available: {e}")
        
        # Playbook tools
        try:
            from mcp_server.tools.playbook_tools import register_playbook_tools
            register_playbook_tools(self)
            logger.info("Playbook tools registered")
        except ImportError as e:
            logger.warning(f"Playbook tools not available: {e}")
        
        # Agent Zero handoff tools
        try:
            from mcp_server.tools.agent_zero_handoff_tools import register_agent_zero_handoff_tools
            register_agent_zero_handoff_tools(self)
            logger.info("Agent Zero handoff tools registered")
        except ImportError as e:
            logger.warning(f"Agent Zero handoff tools not available: {e}")
    
    def _convert_dict_to_tooldef(self) -> None:
        """Convert dict format tools to ToolDefinition objects."""
        for name, tool_data in list(self._tools.items()):
            if isinstance(tool_data, dict) and 'handler' in tool_data:
                self._tools[name] = ToolDefinition(
                    name=tool_data.get('name', name),
                    description=tool_data.get('description', ''),
                    input_schema=tool_data.get('input_schema', {}),
                    handler=tool_data['handler'],
                    dangerous=tool_data.get('dangerous', False),
                    annotations=tool_data.get('annotations', {})
                )
                logger.info(f"Converted {name} to ToolDefinition")
    
    def _merge_extra_tools(self) -> None:
        """Merge extra tools into main tools dict."""
        for name, tool_data in self.extra_tools.items():
            if isinstance(tool_data, dict) and 'handler' in tool_data:
                self._tools[name] = ToolDefinition(
                    name=tool_data.get('name', name),
                    description=tool_data.get('description', ''),
                    input_schema=tool_data.get('input_schema', {}),
                    handler=tool_data['handler'],
                    dangerous=tool_data.get('dangerous', False),
                    annotations=tool_data.get('annotations', {})
                )
                logger.info(f"Merged extra tool: {name}")
        
        total = len(self._tools)
        logger.info(f"Total tools registered: {total}")
    
    def list_tools(self) -> List[ToolDefinition]:
        """List all registered tools."""
        return list(self._tools.values())
    
    def get_tool_definitions(self) -> List[Dict[str, Any]]:
        """Get tool definitions for MCP manifest."""
        definitions = []
        for tool in self.list_tools():
            definitions.append({
                'name': tool.name,
                'description': tool.description,
                'inputSchema': tool.input_schema,
                'annotations': tool.annotations or {}
            })
        return definitions

    def get_tool(self, name: str) -> Optional[ToolDefinition]:
        """Get tool by name."""
        return self._tools.get(name)
    
    async def execute_tool(self, name: str, arguments: Dict[str, Any], user: str = "unknown") -> Dict[str, Any]:
        """Execute tool by name."""
        tool = self.get_tool(name)
        if not tool:
            return {
                'content': [{'type': 'text', 'text': f'Unknown tool: {name}'}],
                'isError': True
            }
        
        logger.info(f"[MCP] execute_tool: name={name}, args={json.dumps(arguments)[:100]}")
        
        try:
            call_args = dict(arguments or {})
            call_args["_user"] = user
            outcome = tool.handler(call_args)
            result = await outcome if inspect.isawaitable(outcome) else outcome
            logger.info(f"[MCP] result: isError={result.get('isError', False)}")
            return result
        except Exception as e:
            logger.error(f"[MCP] error: {e}")
            return {
                'content': [{'type': 'text', 'text': f'Error: {e}'}],
                'isError': True
            }


def register_tools(ssh_client=None) -> MCPTools:
    """Register all MCP tools."""
    return MCPTools(ssh_client)
