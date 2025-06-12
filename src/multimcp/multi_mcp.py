import os
import uvicorn
import json
from typing import Literal,Any,Optional,Dict
from pydantic_settings import BaseSettings

from mcp.server.stdio import stdio_server
from starlette.applications import Starlette
from starlette.routing import Route, Mount
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp.server.sse import SseServerTransport

from src.multimcp.mcp_client import MCPClientManager
from src.multimcp.mcp_proxy import MCPProxyServer
from src.multimcp.single_tool_proxy import SingleToolProxyServer
from src.utils.logger import configure_logging, get_logger

class MCPSettings(BaseSettings):
    """Configuration settings for the MultiMCP server."""
    host: str = "127.0.0.1"
    port: int = 8080
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    transport: Literal["stdio", "sse"] = "stdio"
    sse_server_debug: bool = False
    config: str="./mcp.json"

class MultiMCP:
    def __init__(self, **settings: Any):
        self.settings = MCPSettings(**settings)
        configure_logging(level=self.settings.log_level)
        self.logger = get_logger("MultiMCP")
        self.proxy: Optional[MCPProxyServer] = None
        self.tool_proxies: Dict[str, SingleToolProxyServer] = {}
        self.tool_transports: Dict[str, SseServerTransport] = {}


    async def run(self):
        """Entry point to run the MultiMCP server: loads config, initializes clients, starts server."""
        self.logger.info(f"🚀 Starting MultiMCP with transport: {self.settings.transport}")
        config = self.load_mcp_config(path=self.settings.config)
        if not config:
            self.logger.error("❌ Failed to load MCP config.")
            return
        clients_manager = MCPClientManager()
        clients = await clients_manager.create_clients(config)
        if not clients:
            self.logger.error("❌ No valid clients were created.")
            return

        self.logger.info(f"✅ Connected clients: {list(clients.keys())}")

        try:
            if self.settings.transport == "stdio":
                # For stdio, use the original unified proxy
                self.proxy = await MCPProxyServer.create(clients_manager)
            elif self.settings.transport == "sse":
                # For SSE, create individual proxies per tool
                await self.create_tool_proxies(clients)

            await self.start_server()
        finally:
            await clients_manager.close()

    async def create_tool_proxies(self, clients: Dict[str, Any]) -> None:
        """Create individual proxy servers for each tool."""
        for tool_name, client in clients.items():
            try:
                self.logger.info(f"🔧 Creating proxy for tool: {tool_name}")
                proxy = await SingleToolProxyServer.create(tool_name, client)
                self.tool_proxies[tool_name] = proxy
                
                # Create SSE transport for this tool
                transport = SseServerTransport(f"/{tool_name}/messages/")
                self.tool_transports[tool_name] = transport
                
                self.logger.info(f"✅ Created proxy and transport for {tool_name}")
            except Exception as e:
                self.logger.error(f"❌ Failed to create proxy for {tool_name}: {e}")

    def load_mcp_config(self,path="./mcp.json"):
        """Loads MCP JSON configuration From File."""
        if not os.path.exists(path):
            print(f"Error: {path} does not exist.")
            return None

        with open(path, "r", encoding="utf-8") as file:
            try:
                data = json.load(file)
                return data
            except json.JSONDecodeError as e:
                print(f"Error parsing JSON: {e}")
                return None


    async def start_server(self):
        """Start the proxy server in stdio or SSE mode."""
        if self.settings.transport == "stdio":
            await self.start_stdio_server()
        elif self.settings.transport == "sse":
            await self.start_sse_server()
        else:
            raise ValueError(f"Unsupported transport: {self.settings.transport}")

    async def start_stdio_server(self) -> None:
        """Run the proxy server over stdio."""
        async with stdio_server() as (read_stream, write_stream):
            await self.proxy.run(
                read_stream,
                write_stream,
                self.proxy.create_initialization_options(),
            )

    async def start_sse_server(self) -> None:
        """Run the proxy server over SSE transport with individual tool endpoints."""
        routes = []
        
        # Create individual SSE endpoints for each tool
        for tool_name, proxy in self.tool_proxies.items():
            transport = self.tool_transports[tool_name]
            
            # Create handler for this specific tool (using closure to capture variables)
            def create_tool_handler(tool_proxy, tool_transport, name):
                async def handle_tool_sse(request):
                    async with tool_transport.connect_sse(request.scope, request.receive, request._send) as streams:
                        await tool_proxy.run(
                            streams[0],
                            streams[1],
                            tool_proxy.create_initialization_options(),
                        )
                return handle_tool_sse
            
            # Add routes for this tool
            tool_handler = create_tool_handler(proxy, transport, tool_name)
            routes.append(Route(f"/{tool_name}/sse", endpoint=tool_handler))
            routes.append(Mount(f"/{tool_name}/messages/", app=transport.handle_post_message))
            
            self.logger.info(f"🌐 Created SSE endpoint: /{tool_name}/sse")

        # Add management endpoints
        routes.extend([
            Route("/mcp_servers", endpoint=self.handle_mcp_servers, methods=["GET", "POST"]),
            Route("/mcp_servers/{name}", endpoint=self.handle_mcp_servers, methods=["DELETE"]),
            Route("/mcp_tools", endpoint=self.handle_mcp_tools, methods=["GET"]),
            Route("/tool_endpoints", endpoint=self.handle_tool_endpoints, methods=["GET"])
        ])

        starlette_app = Starlette(
            debug=self.settings.sse_server_debug,
            routes=routes,
        )

        config = uvicorn.Config(
            starlette_app,
            host=self.settings.host,
            port=self.settings.port,
            log_level=self.settings.log_level.lower(),
        )
        server = uvicorn.Server(config)
        await server.serve()

    async def handle_tool_endpoints(self, request: Request) -> JSONResponse:
        """Return the list of available tool endpoints."""
        try:
            endpoints = {}
            for tool_name in self.tool_proxies.keys():
                endpoints[tool_name] = {
                    "sse_endpoint": f"/{tool_name}/sse",
                    "messages_endpoint": f"/{tool_name}/messages/"
                }
            
            return JSONResponse({
                "tool_endpoints": endpoints,
                "total_tools": len(endpoints)
            })
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)

    async def handle_mcp_servers(self, request: Request) -> JSONResponse:
        """Handle GET/POST/DELETE to list, add, or remove MCP clients at runtime."""
        method = request.method

        if method == "GET":
            if self.settings.transport == "sse":
                servers = list(self.tool_proxies.keys())
            else:
                servers = list(self.proxy.client_manager.clients.keys()) if self.proxy else []
            return JSONResponse({"active_servers": servers})

        elif method == "POST":
            return JSONResponse({"error": "Dynamic server addition not yet supported for isolated SSE endpoints"}, status_code=501)

        elif method == "DELETE":
            return JSONResponse({"error": "Dynamic server removal not yet supported for isolated SSE endpoints"}, status_code=501)

        return JSONResponse({"error": f"Unsupported method: {method}"}, status_code=405)

    async def handle_mcp_tools(self, request: Request) -> JSONResponse:
        """Return the list of currently available tools grouped by server."""
        try:
            tools_by_server = {}
            
            if self.settings.transport == "sse":
                # For SSE mode, get tools from individual proxies
                for tool_name, proxy in self.tool_proxies.items():
                    try:
                        tools_by_server[tool_name] = [tool.name for tool in proxy.tools]
                    except Exception as e:
                        tools_by_server[tool_name] = f"❌ Error: {str(e)}"
            else:
                # For stdio mode, use the unified proxy
                if not self.proxy:
                    return JSONResponse({"error": "Proxy not initialized"}, status_code=500)

                for server_name, client in self.proxy.client_manager.clients.items():
                    try:
                        tools = await client.list_tools()
                        tools_by_server[server_name] = [tool.name for tool in tools.tools]
                    except Exception as e:
                        tools_by_server[server_name] = f"❌ Error: {str(e)}"

            return JSONResponse({"tools": tools_by_server})

        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=500)