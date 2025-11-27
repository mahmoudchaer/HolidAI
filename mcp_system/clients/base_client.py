"""Base client for MCP agent communication."""

import httpx
import os
import asyncio
from typing import List, Dict, Any, Optional


class BaseAgentClient:
    """Base client for communicating with MCP server."""
    
    def __init__(self, name: str, allowed_tools: List[str], server_url: str = None):
        """Initialize the agent client.
        
        Args:
            name: Agent name
            allowed_tools: List of tool names this agent can use
            server_url: MCP server URL (defaults to MCP_SERVER_URL env var or http://localhost:8090)
        """
        self.name = name
        self.allowed_tools = allowed_tools
        self.server_url = server_url or os.getenv("MCP_SERVER_URL", "http://localhost:8090")
        self._client: Optional[httpx.AsyncClient] = None
    
    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create httpx client.
        
        Creates a new client if one doesn't exist. If the existing
        client fails, it will be recreated on the next call.
        """
        if self._client is None:
            # Use longer timeout and better connection settings
            timeout = httpx.Timeout(60.0, connect=10.0)
            limits = httpx.Limits(max_keepalive_connections=5, max_connections=10)
            self._client = httpx.AsyncClient(timeout=timeout, limits=limits)
        return self._client
    
    async def _reset_client(self):
        """Reset the HTTP client (close and clear)."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except:
                pass
            self._client = None
    
    def _is_connection_error(self, error: Exception) -> bool:
        """Check if error is a connection-related error that should trigger retry."""
        # Check for httpx connection errors by type
        if isinstance(error, (
            httpx.RemoteProtocolError,
            httpx.ConnectError,
            httpx.ConnectTimeout,
            httpx.ReadTimeout,
            httpx.WriteTimeout,
            httpx.PoolTimeout,
            httpx.NetworkError
        )):
            return True
        
        # Check error message for connection-related issues
        error_str = str(error).lower()
        connection_keywords = [
            "disconnected",
            "connection",
            "timeout",
            "closed",
            "broken",
            "reset",
            "refused",
            "server disconnected"
        ]
        
        return any(keyword in error_str for keyword in connection_keywords)
    
    async def list_tools(self) -> List[Dict[str, Any]]:
        """List available tools for this agent.
        
        Returns:
            List of tool dictionaries with name, description, inputSchema, etc.
        """
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                client = await self._get_client()
                response = await client.get(f"{self.server_url}/tools/list")
                response.raise_for_status()
                data = response.json()
                all_tools = data.get("tools", [])
                
                # Filter tools based on allowed_tools
                filtered_tools = [
                    tool for tool in all_tools
                    if tool["name"] in self.allowed_tools
                ]
                
                return filtered_tools
            except (RuntimeError, AttributeError) as e:
                # If event loop is closed or client is invalid, reset and retry
                if "closed" in str(e).lower() or "Event loop" in str(e):
                    await self._reset_client()
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    raise
                raise
            except Exception as e:
                # Handle connection errors with retry
                if self._is_connection_error(e):
                    await self._reset_client()
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    # Last attempt failed, raise the error
                    raise
                # Non-connection errors are raised immediately
                raise
    
    async def invoke(self, tool_name: str, **kwargs) -> Any:
        """Invoke a tool.
        
        Args:
            tool_name: Name of the tool to invoke
            **kwargs: Tool parameters
            
        Returns:
            Tool result
            
        Raises:
            PermissionError: If tool is not in allowed_tools
        """
        if tool_name not in self.allowed_tools:
            raise PermissionError(
                f"Agent '{self.name}' is not allowed to use tool '{tool_name}'. "
                f"Allowed tools: {self.allowed_tools}"
            )
        
        max_retries = 3
        retry_delay = 0.5
        
        for attempt in range(max_retries):
            try:
                client = await self._get_client()
                payload = {
                    "tool": tool_name,
                    "parameters": kwargs
                }
                
                response = await client.post(f"{self.server_url}/tools/invoke", json=payload)
                response.raise_for_status()
                data = response.json()
                return data.get("result")
            except (RuntimeError, AttributeError) as e:
                # If event loop is closed or client is invalid, reset and retry
                if "closed" in str(e).lower() or "Event loop" in str(e):
                    await self._reset_client()
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    raise
                raise
            except Exception as e:
                # Handle connection errors with retry
                if self._is_connection_error(e):
                    await self._reset_client()
                    if attempt < max_retries - 1:
                        await asyncio.sleep(retry_delay * (attempt + 1))
                        continue
                    # Last attempt failed, raise the error
                    raise
                # Non-connection errors are raised immediately
                raise
    
    async def call_tool(self, tool_name: str, **kwargs) -> Any:
        """Alias for invoke method (for backward compatibility).
        
        Args:
            tool_name: Name of the tool to invoke
            **kwargs: Tool parameters
            
        Returns:
            Tool result
        """
        return await self.invoke(tool_name, **kwargs)
    
    async def close(self):
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

