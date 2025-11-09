"""Main MCP server for Travel Agent Tools."""

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, List, get_origin, get_args, Optional
import uvicorn
from inspect import signature, getdoc
import json
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.hotel_tools import register_hotel_tools
from tools.coordinator_tools import register_coordinator_tools
from tools.tripadvisor_tools import register_tripadvisor_tools
from tools.visa_tools import register_visa_tools
from tools.flight_tools import register_flight_tools


class FastMCP:
    """FastMCP server implementation."""
    
    def __init__(self, name: str):
        """Initialize the FastMCP server.
        
        Args:
            name: Name of the MCP server
        """
        self.name = name
        self.app = FastAPI(title=name)
        self.tools: Dict[str, Any] = {}
        self._setup_routes()
    
    def tool(self, description: Optional[str] = None):
        """Decorator to register a tool.
        
        Args:
            description: Optional description for the tool. If not provided,
                        will be extracted from the function's docstring.
        
        Returns:
            Decorator function
        """
        def decorator(func):
            tool_name = func.__name__
            sig = signature(func)
            
            # Extract parameter schema
            parameters = {}
            required = []
            for param_name, param in sig.parameters.items():
                param_type = "string"  # Default to string
                if param.annotation != sig.empty:
                    annotation = param.annotation
                    # Handle typing module types
                    origin = get_origin(annotation)
                    if origin is not None:
                        if origin == dict or origin == Dict:
                            param_type = "object"
                        elif origin == list or origin == List:
                            param_type = "array"
                    elif annotation == int:
                        param_type = "integer"
                    elif annotation == float:
                        param_type = "number"
                    elif annotation == bool:
                        param_type = "boolean"
                    elif annotation == dict:
                        param_type = "object"
                    elif annotation == list:
                        param_type = "array"
                    elif str(annotation).startswith("typing.Dict") or str(annotation) == "Dict":
                        param_type = "object"
                    elif str(annotation).startswith("typing.List") or str(annotation) == "List":
                        param_type = "array"
                
                param_info = {
                    "type": param_type,
                    "description": f"Parameter: {param_name}"
                }
                
                if param.default == sig.empty:
                    required.append(param_name)
                
                parameters[param_name] = param_info
            
            # Extract return type and build output schema
            return_type = sig.return_annotation
            if return_type == sig.empty:
                return_type = "object"
            
            # Convert return type annotation to schema type
            output_type = "object"  # Default
            if return_type != sig.empty:
                # Handle typing module types
                origin = get_origin(return_type)
                if origin is not None:
                    if origin == dict or origin == Dict:
                        output_type = "object"
                    elif origin == list or origin == List:
                        output_type = "array"
                elif return_type == int:
                    output_type = "integer"
                elif return_type == float:
                    output_type = "number"
                elif return_type == bool:
                    output_type = "boolean"
                elif return_type == str:
                    output_type = "string"
                elif return_type == dict:
                    output_type = "object"
                elif return_type == list:
                    output_type = "array"
            
            # Get description from parameter, docstring, or default
            if description:
                tool_description = description
            else:
                tool_description = getdoc(func) or f"Tool: {tool_name}"
            
            # Register the tool with full metadata
            self.tools[tool_name] = {
                "name": tool_name,
                "description": tool_description,
                "inputSchema": {
                    "type": "object",
                    "properties": parameters,
                    "required": required
                },
                "returns": {
                    "type": output_type,
                    "description": f"Result from {tool_name}"
                }
            }
            
            # Store the function for invocation
            self.tools[tool_name]["_func"] = func
            
            return func  # Return the original function so it can still be called
        
        return decorator  # Return the decorator function
    
    def _setup_routes(self):
        """Setup FastAPI routes."""
        
        @self.app.get("/")
        async def root():
            return {"server": self.name, "status": "running"}
        
        @self.app.get("/tools/list")
        async def list_tools():
            """List all available tools with full metadata.
            
            Returns:
                JSON response with tools array, each containing:
                - name: Tool name
                - description: Tool description
                - inputSchema: JSON schema for input parameters
                - returns: JSON schema for output
            """
            tools_list = [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "inputSchema": tool["inputSchema"],
                    "returns": tool.get("returns", {"type": "object"})
                }
                for tool in self.tools.values()
                if "_func" in tool
            ]
            return {"tools": tools_list}
        
        @self.app.get("/tools/metadata")
        async def get_tool_metadata():
            """Get metadata for all tools."""
            return {"tools": self.tools}
        
        @self.app.post("/tools/invoke")
        async def invoke_tool(request: Dict[str, Any]):
            """Invoke a tool.
            
            Expected request format:
            {
                "tool": "tool_name",
                "parameters": {...}
            }
            """
            tool_name = request.get("tool")
            parameters = request.get("parameters", {})
            
            if tool_name not in self.tools:
                raise HTTPException(status_code=404, detail=f"Tool '{tool_name}' not found")
            
            tool_func = self.tools[tool_name].get("_func")
            if not tool_func:
                raise HTTPException(status_code=500, detail=f"Tool '{tool_name}' not callable")
            
            try:
                result = tool_func(**parameters)
                return {"result": result}
            except TypeError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid parameters for tool '{tool_name}': {str(e)}"
                )
            except Exception as e:
                raise HTTPException(
                    status_code=500,
                    detail=f"Error executing tool '{tool_name}': {str(e)}"
                )
    
    def run(self, transport: str = "http", host: str = "0.0.0.0", port: int = 8090):
        """Run the MCP server.
        
        Args:
            transport: Transport type (currently only "http" supported)
            host: Host to bind to
            port: Port to bind to
        """
        if transport != "http":
            raise ValueError(f"Transport '{transport}' not supported. Use 'http'.")
        
        print(f"Starting {self.name} MCP server on http://{host}:{port}")
        print(f"Available tools: {', '.join(self.tools.keys())}")
        uvicorn.run(self.app, host=host, port=port)


# Create MCP instance
mcp = FastMCP("TravelAgentTools")

# Register tool groups
register_hotel_tools(mcp)
register_coordinator_tools(mcp)
register_tripadvisor_tools(mcp)
register_visa_tools(mcp)
register_flight_tools(mcp)


if __name__ == "__main__":
    mcp.run(transport="http", host="0.0.0.0", port=8090)

