# app/services/agentic_tools.py
import httpx
import math
import json
from typing import Dict, Any, List
import os
from dotenv import load_dotenv

load_dotenv()

class ToolRegistry:
    def __init__(self):
        self.tools = {}
    
    def register_tool(self, name: str, function: callable, schema: Dict): # type: ignore
        self.tools[name] = {"function": function, "schema": schema}
    
    def get_tool_schemas(self) -> List[Dict]:
        return [tool["schema"] for tool in self.tools.values()]

tool_registry = ToolRegistry()

# Tavily Search Tool
async def tavily_search_function(params: Dict) -> Dict[str, Any]:
    """Search web for current information using Tavily API"""
    query = params.get("query", "")
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.tavily.com/search",
                json={
                    "api_key": os.getenv("TAVILY_API_KEY", ""),
                    "query": query,
                    "search_depth": "advanced",
                    "include_answer": True,
                    "include_raw_content": False,
                    "max_results": 5
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                return {"success": False, "error": f"API error: {response.status_code}"}
            
            results = response.json()
            
            # Format results
            formatted_results = []
            
            # Include answer if available
            if results.get("answer"):
                formatted_results.append(f"Direct Answer: {results['answer']}")
            
            # Include search results
            for result in results.get("results", [])[:3]:
                title = result.get("title", "No title")
                content = result.get("content", "No content")
                url = result.get("url", "")
                formatted_results.append(f"{title}: {content} [Source: {url}]")
            
            return {
                "success": True,
                "results": formatted_results,
                "query": query,
                "sources": [r.get("url", "") for r in results.get("results", [])[:3]]
            }
            
    except Exception as e:
        return {"success": False, "error": str(e)}

TAVILY_SEARCH_SCHEMA = {
    "type": "function",
    "function": {
        "name": "tavily_search",
        "description": "Search the web for current information, news, or real-time data. Perfect for finding latest trends, market data, or recent developments.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query for finding relevant information"}
            },
            "required": ["query"]
        }
    }
}

# Calculator Tool (unchanged)
async def calculator_function(params: Dict) -> Dict[str, Any]:
    """Perform mathematical calculations"""
    expression = params.get("expression", "")
    
    # Safe evaluation
    allowed_ops = {
        'abs': abs, 'round': round, 'min': min, 'max': max,
        'sum': sum, 'pow': pow, 'sqrt': math.sqrt
    }
    
    try:
        # Remove dangerous operations
        safe_expression = expression.replace('import', '').replace('__', '')
        result = eval(safe_expression, {"__builtins__": {}}, allowed_ops)
        return {"success": True, "result": result, "expression": expression}
    except Exception as e:
        return {"success": False, "error": str(e)}

CALCULATOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "calculator",
        "description": "Perform mathematical calculations and computations",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Mathematical expression to evaluate"}
            },
            "required": ["expression"]
        }
    }
}

# SQL Query Tool (Mock - unchanged)
async def sql_query_function(params: Dict) -> Dict[str, Any]:
    """Query database for structured data"""
    query = params.get("query", "")
    
    # Mock implementation - replace with real DB connection
    if "revenue" in query.lower():
        return {
            "success": True,
            "results": [{"quarter": "Q3", "revenue": 1500000, "growth": "15%"}],
            "query": query
        }
    
    return {"success": False, "error": "No matching data found"}

SQL_QUERY_SCHEMA = {
    "type": "function",
    "function": {
        "name": "sql_query",
        "description": "Query database for structured business data",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "SQL query or natural language request"}
            },
            "required": ["query"]
        }
    }
}

# Register all tools - now with Tavily instead of web_search
tool_registry.register_tool("tavily_search", tavily_search_function, TAVILY_SEARCH_SCHEMA)
tool_registry.register_tool("calculator", calculator_function, CALCULATOR_SCHEMA)
tool_registry.register_tool("sql_query", sql_query_function, SQL_QUERY_SCHEMA)