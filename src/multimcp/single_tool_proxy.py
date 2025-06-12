from typing import Any, Optional
from mcp import server, types
from mcp.client.session import ClientSession
from src.utils.logger import get_logger


class SingleToolProxyServer(server.Server):
    """An MCP Proxy Server that forwards requests to a single remote MCP server."""

    def __init__(self, tool_name: str, client: ClientSession):
        super().__init__(f"SingleTool proxy Server for {tool_name}")
        self.tool_name = tool_name
        self.client = client
        self.capabilities: Optional[types.ServerCapabilities] = None
        self.tools: list[types.Tool] = []
        self.prompts: list[types.Prompt] = []
        self.resources: list[types.Resource] = []
        self._register_request_handlers()
        self.logger = get_logger(f"SingleToolProxy.{tool_name}")

    @classmethod
    async def create(cls, tool_name: str, client: ClientSession) -> "SingleToolProxyServer":
        """Factory method to create and initialize the proxy with a single client."""
        proxy = cls(tool_name, client)
        await proxy.initialize_client()
        return proxy

    async def initialize_client(self) -> None:
        """Initialize the remote client and store its capabilities."""
        try:
            self.logger.info(f"Initializing client for {self.tool_name}")
            result = await self.client.initialize()
            self.capabilities = result.capabilities

            if result.capabilities.tools:
                tools_result = await self.client.list_tools()
                self.tools = tools_result.tools

            if result.capabilities.prompts:
                prompts_result = await self.client.list_prompts()
                self.prompts = prompts_result.prompts

            if result.capabilities.resources:
                resources_result = await self.client.list_resources()
                self.resources = resources_result.resources

            self.logger.info(f"✅ Initialized {self.tool_name} with {len(self.tools)} tools, {len(self.prompts)} prompts, {len(self.resources)} resources")

        except Exception as e:
            self.logger.error(f"❌ Failed to initialize client {self.tool_name}: {e}")
            raise

    ## Tools capabilities
    async def _list_tools(self, _: Any) -> types.ServerResult:
        """Return tools from this specific MCP server."""
        return types.ServerResult(tools=self.tools)

    async def _call_tool(self, req: types.CallToolRequest) -> types.ServerResult:
        """Invoke a tool on this MCP server."""
        tool_name = req.params.name
        
        # Check if the tool exists in this server
        tool_exists = any(tool.name == tool_name for tool in self.tools)
        
        if tool_exists:
            try:
                self.logger.info(f"✅ Calling tool '{tool_name}' on {self.tool_name}")
                result = await self.client.call_tool(tool_name, req.params.arguments or {})
                return types.ServerResult(result)
            except Exception as e:
                self.logger.error(f"❌ Failed to call tool '{tool_name}': {e}")
                return types.ServerResult(
                    content=[types.TextContent(type="text", text=f"Error calling tool '{tool_name}': {str(e)}")],
                    isError=True,
                )
        else:
            self.logger.error(f"⚠️ Tool '{tool_name}' not found in {self.tool_name}.")
            return types.ServerResult(
                content=[types.TextContent(type="text", text=f"Tool '{tool_name}' not found in {self.tool_name}!")],
                isError=True,
            )

    ## Prompts capabilities
    async def _list_prompts(self, _: Any) -> types.ServerResult:
        """Return prompts from this specific MCP server."""
        return types.ServerResult(prompts=self.prompts)

    async def _get_prompt(self, req: types.GetPromptRequest) -> types.ServerResult:
        """Fetch a specific prompt from this MCP server."""
        prompt_name = req.params.name
        
        # Check if the prompt exists in this server
        prompt_exists = any(prompt.name == prompt_name for prompt in self.prompts)
        
        if prompt_exists:
            try:
                result = await self.client.get_prompt(req.params)
                return types.ServerResult(result)
            except Exception as e:
                self.logger.error(f"❌ Failed to get prompt '{prompt_name}': {e}")
                return types.ServerResult(
                    content=[types.TextContent(type="text", text=f"Error getting prompt '{prompt_name}': {str(e)}")],
                    isError=True,
                )
        else:
            self.logger.error(f"⚠️ Prompt '{prompt_name}' not found in {self.tool_name}.")
            return types.ServerResult(
                content=[types.TextContent(type="text", text=f"Prompt '{prompt_name}' not found in {self.tool_name}!")],
                isError=True,
            )

    async def _complete(self, req: types.CompleteRequest) -> types.ServerResult:
        """Execute a prompt completion on this MCP server."""
        prompt_name = req.params.prompt
        
        # Check if the prompt exists in this server
        prompt_exists = any(prompt.name == prompt_name for prompt in self.prompts)
        
        if prompt_exists:
            try:
                result = await self.client.complete(req.params)
                return types.ServerResult(result)
            except Exception as e:
                self.logger.error(f"❌ Failed to complete prompt '{prompt_name}': {e}")
                return types.ServerResult(
                    content=[types.TextContent(type="text", text=f"Error completing prompt '{prompt_name}': {str(e)}")],
                    isError=True,
                )
        else:
            self.logger.error(f"⚠️ Prompt '{prompt_name}' not found for completion in {self.tool_name}.")
            return types.ServerResult(
                content=[types.TextContent(type="text", text=f"Prompt '{prompt_name}' not found for completion in {self.tool_name}!")],
                isError=True,
            )

    ## Resources capabilities
    async def _list_resources(self, _: Any) -> types.ServerResult:
        """Return resources from this specific MCP server."""
        return types.ServerResult(resources=self.resources)

    async def _read_resource(self, req: types.ReadResourceRequest) -> types.ServerResult:
        """Read a resource from this MCP server."""
        resource_uri = req.params.uri
        
        # Check if the resource exists in this server
        resource_exists = any(resource.uri == resource_uri for resource in self.resources)
        
        if resource_exists:
            try:
                result = await self.client.read_resource(req.params)
                return types.ServerResult(result)
            except Exception as e:
                self.logger.error(f"❌ Failed to read resource '{resource_uri}': {e}")
                return types.ServerResult(
                    content=[types.TextContent(type="text", text=f"Error reading resource '{resource_uri}': {str(e)}")],
                    isError=True,
                )
        else:
            self.logger.error(f"⚠️ Resource '{resource_uri}' not found in {self.tool_name}.")
            return types.ServerResult(
                content=[types.TextContent(type="text", text=f"Resource '{resource_uri}' not found in {self.tool_name}!")],
                isError=True,
            )

    async def _subscribe_resource(self, req: types.SubscribeRequest) -> types.ServerResult:
        """Subscribe to a resource for updates on this MCP server."""
        uri = req.params.uri
        
        # Check if the resource exists in this server
        resource_exists = any(resource.uri == uri for resource in self.resources)
        
        if resource_exists:
            try:
                await self.client.subscribe_resource(uri)
                return types.ServerResult(types.EmptyResult())
            except Exception as e:
                self.logger.error(f"❌ Failed to subscribe to resource '{uri}': {e}")
                return types.ServerResult(
                    content=[types.TextContent(type="text", text=f"Error subscribing to resource '{uri}': {str(e)}")],
                    isError=True,
                )
        else:
            self.logger.error(f"⚠️ Resource '{uri}' not found for subscription in {self.tool_name}.")
            return types.ServerResult(
                content=[types.TextContent(type="text", text=f"Resource '{uri}' not found for subscription in {self.tool_name}!")],
                isError=True,
            )

    async def _unsubscribe_resource(self, req: types.UnsubscribeRequest) -> types.ServerResult:
        """Unsubscribe from a previously subscribed resource."""
        uri = req.params.uri
        
        # Check if the resource exists in this server
        resource_exists = any(resource.uri == uri for resource in self.resources)
        
        if resource_exists:
            try:
                await self.client.unsubscribe_resource(uri)
                return types.ServerResult(types.EmptyResult())
            except Exception as e:
                self.logger.error(f"❌ Failed to unsubscribe from resource '{uri}': {e}")
                return types.ServerResult(
                    content=[types.TextContent(type="text", text=f"Error unsubscribing from resource '{uri}': {str(e)}")],
                    isError=True,
                )
        else:
            self.logger.error(f"⚠️ Resource '{uri}' not found for unsubscription in {self.tool_name}.")
            return types.ServerResult(
                content=[types.TextContent(type="text", text=f"Resource '{uri}' not found for unsubscription in {self.tool_name}!")],
                isError=True,
            )

    # Utilization function
    async def _set_logging_level(self, req: types.SetLevelRequest) -> types.ServerResult:
        """Set logging level on this client."""
        try:
            await self.client.set_logging_level(req.params.level)
            return types.ServerResult(types.EmptyResult())
        except Exception as e:
            self.logger.error(f"❌ Failed to set logging level on client: {e}")
            return types.ServerResult(
                content=[types.TextContent(type="text", text=f"Error setting logging level: {str(e)}")],
                isError=True,
            )

    async def _send_progress_notification(self, req: types.ProgressNotification) -> None:
        """Relay a progress update to this backend client."""
        try:
            await self.client.send_progress_notification(
                req.params.progressToken,
                req.params.progress,
                req.params.total,
            )
        except Exception as e:
            self.logger.error(f"❌ Failed to send progress notification: {e}")

    def _register_request_handlers(self) -> None:
        """Dynamically registers handlers for all MCP requests."""

        # Register all request handlers
        self.request_handlers[types.ListPromptsRequest] = self._list_prompts
        self.request_handlers[types.GetPromptRequest]   = self._get_prompt
        self.request_handlers[types.CompleteRequest]    = self._complete

        self.request_handlers[types.ListResourcesRequest] = self._list_resources
        self.request_handlers[types.ReadResourceRequest]  = self._read_resource
        self.request_handlers[types.SubscribeRequest]     = self._subscribe_resource
        self.request_handlers[types.UnsubscribeRequest]   = self._unsubscribe_resource

        self.request_handlers[types.ListToolsRequest] = self._list_tools
        self.request_handlers[types.CallToolRequest]  = self._call_tool

        self.notification_handlers[types.ProgressNotification] = self._send_progress_notification

        self.request_handlers[types.SetLevelRequest] = self._set_logging_level