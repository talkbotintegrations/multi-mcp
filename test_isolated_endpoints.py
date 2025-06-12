#!/usr/bin/env python3
"""
Test script to verify that isolated SSE endpoints work correctly.
"""
import asyncio
import json
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession


async def test_endpoint(tool_name: str, endpoint_url: str):
    """Test a specific tool endpoint."""
    print(f"Testing {tool_name} at {endpoint_url}")
    
    try:
        async with sse_client(url=endpoint_url) as (read, write):
            async with ClientSession(read, write) as session:
                # Initialize the session
                result = await session.initialize()
                print(f"  ✅ {tool_name} initialized successfully")
                print(f"  📋 Capabilities: tools={bool(result.capabilities.tools)}, prompts={bool(result.capabilities.prompts)}, resources={bool(result.capabilities.resources)}")
                
                # List tools
                if result.capabilities.tools:
                    tools = await session.list_tools()
                    tool_names = [tool.name for tool in tools.tools]
                    print(f"  🔧 Available tools: {tool_names}")
                
                return True
                
    except Exception as e:
        print(f"  ❌ {tool_name} failed: {e}")
        return False


async def test_parallel_access():
    """Test that multiple endpoints can be accessed in parallel."""
    print("🚀 Testing parallel access to multiple endpoints...")
    
    endpoints = [
        ("weather", "http://localhost:12000/weather/sse"),
        ("calculator", "http://localhost:12000/calculator/sse"),
        ("aider", "http://localhost:12000/aider/sse"),
        ("filesystem", "http://localhost:12000/filesystem/sse"),
        ("database", "http://localhost:12000/database/sse"),
    ]
    
    # Test all endpoints in parallel
    tasks = [test_endpoint(name, url) for name, url in endpoints]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful = sum(1 for result in results if result is True)
    total = len(endpoints)
    
    print(f"\n📊 Results: {successful}/{total} endpoints working correctly")
    
    if successful == total:
        print("✅ All endpoints are working correctly and can be accessed in parallel!")
        return True
    else:
        print("❌ Some endpoints failed")
        return False


if __name__ == "__main__":
    success = asyncio.run(test_parallel_access())
    exit(0 if success else 1)