"""Base client for MCP agent clients."""

from typing import List, Dict, Any
import httpx


class BaseAgentClient:
    """Base class for agent clients that interact with the MCP server."""
    
    def __init__(self, name: str, allowed_tools: List[str], server_url: str = "http://localhost:8090"):
        """Initialize the agent client.
        
        Args:
            name: Name of the agent (e.g., "HotelAgent")
            allowed_tools: List of tool names this agent is allowed to use
            server_url: Base URL of the MCP server
        """
        self.name = name
        self.allowed_tools = set(allowed_tools)
        self.server_url = server_url
        self._http_client = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create an HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(base_url=self.server_url, timeout=30.0)
        return self._http_client
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List all tools available to this agent.
        
        Dynamically fetches tool metadata from the MCP server and filters
        based on the agent's allowed_tools list. This ensures the agent
        always has the latest tool descriptions, input schemas, and output schemas.
        
        Returns:
            List of tool metadata dictionaries (filtered to allowed tools only).
            Each tool dict contains:
            - name: Tool name
            - description: Tool description
            - inputSchema: JSON schema for input parameters
            - returns: JSON schema for output
        """
        try:
            client = await self._get_client()
            response = await client.get("/tools/list")
            response.raise_for_status()
            data = response.json()
            
            # Handle both {"tools": [...]} and [...] formats
            all_tools = data.get("tools", data) if isinstance(data, dict) else data
            
            # Filter to only allowed tools - this is the key MCP flow step
            filtered_tools = [
                tool for tool in all_tools 
                if tool.get("name") in self.allowed_tools
            ]
            return filtered_tools
        except Exception as e:
            # Fallback: return minimal tool info based on allowed_tools list
            # This should only happen if the server is unavailable
            print(f"Warning: Could not fetch tools from server ({e}). Using fallback.")
            return [
                {"name": tool_name, "description": f"Tool: {tool_name}", "inputSchema": {}, "returns": {"type": "object"}}
                for tool_name in self.allowed_tools
            ]
    
    async def call_tool(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Call a tool with the given parameters.
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Tool-specific parameters
            
        Returns:
            Tool execution result
            
        Raises:
            PermissionError: If the agent is not allowed to use this tool
        """
        if tool_name not in self.allowed_tools:
            raise PermissionError(
                f"{self.name} is not allowed to use tool '{tool_name}'. "
                f"Allowed tools: {', '.join(sorted(self.allowed_tools))}"
            )
        
        try:
            client = await self._get_client()
            response = await client.post(
                "/tools/invoke",
                json={"tool": tool_name, "parameters": kwargs}
            )
            response.raise_for_status()
            result = response.json()
            
            # Handle both {"result": ...} and direct result formats
            if isinstance(result, dict) and "result" in result:
                return result["result"]
            return result
        except httpx.HTTPStatusError as e:
            error_detail = "Unknown error"
            try:
                error_detail = e.response.json().get("detail", str(e))
            except:
                error_detail = str(e)
            raise RuntimeError(f"Failed to call tool '{tool_name}': {error_detail}")
        except httpx.HTTPError as e:
            raise RuntimeError(f"Failed to call tool '{tool_name}': {e}")
    
    async def invoke(self, tool_name: str, **kwargs) -> Dict[str, Any]:
        """Invoke a tool (alias for call_tool for MCP naming consistency).
        
        Args:
            tool_name: Name of the tool to call
            **kwargs: Tool-specific parameters
            
        Returns:
            Tool execution result
            
        Raises:
            PermissionError: If the agent is not allowed to use this tool
        """
        return await self.call_tool(tool_name, **kwargs)
    
    async def close(self):
        """Close the client connection."""
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

