#!/usr/bin/env python3
"""
Example client demonstrating how to connect to isolated SSE endpoints.
"""
import asyncio
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession


async def connect_to_aider_tool():
    """Example: Connect to the Aider tool via its isolated SSE endpoint."""
    print("🔧 Connecting to Aider tool...")
    
    async with sse_client(url="http://localhost:8080/aider/sse") as (read, write):
        async with ClientSession(read, write) as session:
            # Initialize the session
            result = await session.initialize()
            print(f"✅ Connected to Aider tool")
            
            # List available tools
            if result.capabilities.tools:
                tools = await session.list_tools()
                print(f"📋 Available tools: {[tool.name for tool in tools.tools]}")
                
                # Example: Call a tool (if available)
                if tools.tools:
                    tool_name = tools.tools[0].name
                    print(f"🚀 Calling tool: {tool_name}")
                    
                    # Example tool call (adjust arguments based on your tool)
                    try:
                        result = await session.call_tool(tool_name, {"input": "test"})
                        print(f"📤 Tool result: {result}")
                    except Exception as e:
                        print(f"⚠️ Tool call failed: {e}")


async def connect_to_multiple_tools():
    """Example: Connect to multiple tools in parallel."""
    print("🚀 Connecting to multiple tools in parallel...")
    
    async def connect_to_tool(tool_name: str, url: str):
        try:
            async with sse_client(url=url) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    tools = await session.list_tools()
                    tool_names = [tool.name for tool in tools.tools]
                    print(f"✅ {tool_name}: {tool_names}")
                    return tool_names
        except Exception as e:
            print(f"❌ {tool_name} failed: {e}")
            return []
    
    # Connect to multiple tools simultaneously
    tasks = [
        connect_to_tool("weather", "http://localhost:8080/weather/sse"),
        connect_to_tool("calculator", "http://localhost:8080/calculator/sse"),
        connect_to_tool("aider", "http://localhost:8080/aider/sse"),
    ]
    
    results = await asyncio.gather(*tasks, return_exceptions=True)
    print(f"📊 Connected to {len([r for r in results if isinstance(r, list)])} tools successfully")


async def discover_available_endpoints():
    """Example: Discover available tool endpoints dynamically."""
    import httpx
    
    print("🔍 Discovering available tool endpoints...")
    
    async with httpx.AsyncClient() as client:
        response = await client.get("http://localhost:8080/tool_endpoints")
        if response.status_code == 200:
            data = response.json()
            endpoints = data["tool_endpoints"]
            
            print(f"📋 Found {len(endpoints)} tool endpoints:")
            for tool_name, info in endpoints.items():
                print(f"  • {tool_name}: {info['sse_endpoint']}")
            
            return endpoints
        else:
            print(f"❌ Failed to discover endpoints: {response.status_code}")
            return {}


async def main():
    """Main example function."""
    print("🌟 Multi-MCP Isolated SSE Endpoints Example\n")
    
    try:
        # 1. Discover available endpoints
        endpoints = await discover_available_endpoints()
        print()
        
        # 2. Connect to multiple tools in parallel
        if endpoints:
            await connect_to_multiple_tools()
            print()
        
        # 3. Connect to a specific tool (Aider example)
        if "aider" in endpoints:
            await connect_to_aider_tool()
        
    except Exception as e:
        print(f"❌ Example failed: {e}")
        print("\n💡 Make sure the MultiMCP server is running:")
        print("   python main.py --transport sse --host 0.0.0.0 --port 8080")


if __name__ == "__main__":
    asyncio.run(main())