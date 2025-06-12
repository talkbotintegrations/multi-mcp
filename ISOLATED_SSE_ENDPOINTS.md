# Isolated SSE Endpoints Architecture

## Overview

The MultiMCP server now supports isolated SSE endpoints for each configured MCP tool, allowing for independent access and parallel usage of different tools.

## Key Changes

### Before (Unified Architecture)
- Single SSE endpoint: `/sse`
- All tools accessible through one proxy server
- Tools were namespaced as `server_name::tool_name`
- Single message endpoint: `/messages/`

### After (Isolated Architecture)
- Individual SSE endpoints per tool: `/{tool_name}/sse`
- Each tool has its own proxy server and SSE transport
- Tools maintain their original names (no namespacing needed)
- Individual message endpoints: `/{tool_name}/messages/`

## Endpoints

### Tool-Specific SSE Endpoints
Each configured MCP tool gets its own isolated SSE endpoint:

- `/weather/sse` - Weather tool SSE endpoint
- `/calculator/sse` - Calculator tool SSE endpoint  
- `/aider/sse` - Aider tool SSE endpoint
- `/filesystem/sse` - Filesystem tool SSE endpoint
- `/database/sse` - Database tool SSE endpoint

### Management Endpoints
- `GET /tool_endpoints` - List all available tool endpoints
- `GET /mcp_servers` - List active servers
- `GET /mcp_tools` - List tools grouped by server

### Example Response from `/tool_endpoints`:
```json
{
    "tool_endpoints": {
        "weather": {
            "sse_endpoint": "/weather/sse",
            "messages_endpoint": "/weather/messages/"
        },
        "calculator": {
            "sse_endpoint": "/calculator/sse", 
            "messages_endpoint": "/calculator/messages/"
        },
        "aider": {
            "sse_endpoint": "/aider/sse",
            "messages_endpoint": "/aider/messages/"
        }
    },
    "total_tools": 3
}
```

## Benefits

### 1. **Isolation**
- Each tool operates independently
- No cross-tool interference
- Cleaner tool naming (no namespacing required)

### 2. **Parallelization**
- Multiple tools can be accessed simultaneously
- Each endpoint handles its own connections
- Improved scalability for concurrent usage

### 3. **Flexibility**
- Configure unique SSE URLs per tool
- Independent tool management
- Easier debugging and monitoring

### 4. **Backward Compatibility**
- STDIO mode still uses unified proxy
- Existing configurations work unchanged
- Gradual migration path available

## Usage Examples

### Connecting to a Specific Tool
```python
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

async def connect_to_aider():
    async with sse_client(url="http://localhost:8080/aider/sse") as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            # Use aider-specific tools
```

### Parallel Tool Access
```python
import asyncio

async def use_multiple_tools():
    # Connect to multiple tools simultaneously
    weather_task = connect_to_tool("http://localhost:8080/weather/sse")
    calc_task = connect_to_tool("http://localhost:8080/calculator/sse")
    aider_task = connect_to_tool("http://localhost:8080/aider/sse")
    
    # All tools can be used in parallel
    results = await asyncio.gather(weather_task, calc_task, aider_task)
```

## Configuration

The server automatically creates isolated endpoints for each tool defined in your MCP configuration:

```json
{
  "mcpServers": {
    "aider": {
      "command": "aider",
      "args": ["--mcp"]
    },
    "weather": {
      "command": "python",
      "args": ["./weather_tool.py"]
    },
    "calculator": {
      "url": "http://localhost:9000/sse"
    }
  }
}
```

This configuration will create:
- `/aider/sse`
- `/weather/sse` 
- `/calculator/sse`

## Transport Modes

### SSE Mode (Isolated Endpoints)
```bash
python main.py --transport sse --host 0.0.0.0 --port 8080
```
- Creates isolated endpoints per tool
- Supports parallel access
- Recommended for production use

### STDIO Mode (Unified Proxy)
```bash
python main.py --transport stdio
```
- Uses original unified proxy architecture
- Single point of access
- Useful for development and testing

## Implementation Details

### Architecture Components

1. **SingleToolProxyServer**: Individual proxy server per tool
2. **Tool-specific SSE transports**: Isolated message handling
3. **Dynamic routing**: Automatic endpoint creation
4. **Parallel initialization**: Concurrent tool setup

### Key Files Modified
- `src/multimcp/multi_mcp.py` - Main server logic
- `src/multimcp/single_tool_proxy.py` - Individual tool proxy (new)
- `main.py` - CLI interface (unchanged)

## Testing

Run the test script to verify all endpoints work correctly:

```bash
python test_isolated_endpoints.py
```

This will test:
- Individual endpoint connectivity
- Parallel access capability
- Tool isolation
- MCP protocol compliance

## Migration Guide

### From Unified to Isolated Endpoints

1. **Update client URLs**: Change from `/sse` to `/{tool_name}/sse`
2. **Remove tool namespacing**: Use original tool names instead of `server::tool`
3. **Update message endpoints**: Change from `/messages/` to `/{tool_name}/messages/`

### Example Migration
```python
# Before (unified)
url = "http://localhost:8080/sse"
tool_name = "weather::get_weather"

# After (isolated)  
url = "http://localhost:8080/weather/sse"
tool_name = "get_weather"
```

## Troubleshooting

### Common Issues

1. **Endpoint not found (404)**
   - Verify tool is configured in MCP config
   - Check server logs for initialization errors
   - Ensure tool name matches configuration

2. **Connection refused**
   - Verify server is running in SSE mode
   - Check host/port configuration
   - Ensure firewall allows connections

3. **Tool not responding**
   - Check individual tool logs
   - Verify tool process is running
   - Test tool independently

### Debug Commands
```bash
# List available endpoints
curl http://localhost:8080/tool_endpoints

# Check server status
curl http://localhost:8080/mcp_servers

# List tools per server
curl http://localhost:8080/mcp_tools

# Test specific endpoint
curl -I http://localhost:8080/aider/sse
```