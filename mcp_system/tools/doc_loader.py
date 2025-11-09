"""Documentation loader for MCP tools."""

import json
import os
from typing import Dict, Any, Optional


def get_doc(tool_name: str, category: str = "hotel") -> str:
    """Load tool description from JSON documentation file.
    
    Args:
        tool_name: Name of the tool (e.g., "get_hotel_rates")
        category: Category of the tool (e.g., "hotel")
        
    Returns:
        Tool description string, or empty string if not found
    """
    try:
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to mcp_system, then into tool_docs
        docs_dir = os.path.join(os.path.dirname(current_dir), "tool_docs")
        docs_file = os.path.join(docs_dir, f"{category}_docs.json")
        
        with open(docs_file, "r", encoding="utf-8") as f:
            docs = json.load(f)
        
        tool_doc = docs.get(tool_name, {})
        return tool_doc.get("description", "")
    except FileNotFoundError:
        print(f"Warning: Documentation file not found for {category}_docs.json")
        return ""
    except json.JSONDecodeError as e:
        print(f"Warning: Error parsing JSON in {category}_docs.json: {e}")
        return ""
    except Exception as e:
        print(f"Warning: Error loading documentation for {tool_name}: {e}")
        return ""


def get_tool_metadata(tool_name: str, category: str = "hotel") -> Dict[str, Any]:
    """Load full tool metadata (description, inputs, outputs, examples) from JSON.
    
    Args:
        tool_name: Name of the tool (e.g., "get_hotel_rates")
        category: Category of the tool (e.g., "hotel")
        
    Returns:
        Dictionary containing tool metadata, or empty dict if not found
    """
    try:
        # Get the directory where this file is located
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up one level to mcp_system, then into tool_docs
        docs_dir = os.path.join(os.path.dirname(current_dir), "tool_docs")
        docs_file = os.path.join(docs_dir, f"{category}_docs.json")
        
        with open(docs_file, "r", encoding="utf-8") as f:
            docs = json.load(f)
        
        return docs.get(tool_name, {})
    except FileNotFoundError:
        print(f"Warning: Documentation file not found for {category}_docs.json")
        return {}
    except json.JSONDecodeError as e:
        print(f"Warning: Error parsing JSON in {category}_docs.json: {e}")
        return {}
    except Exception as e:
        print(f"Warning: Error loading metadata for {tool_name}: {e}")
        return {}

