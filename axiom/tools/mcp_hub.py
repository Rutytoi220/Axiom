import asyncio
import json
import logging
import subprocess
import threading
import concurrent.futures
from pathlib import Path
from typing import Dict, Any, Optional
from axiom.tools.mcp_sse_client import MCPSSEClient
logger = logging.getLogger(__name__)

class MCPHub:
    """Dynamic Model Context Protocol (MCP) Client Hub."""

    def __init__(self, registry):
        """Auto-generated docstring.

Args:
    registry: Argument.

Returns:
    Return value.
"""
        self.registry = registry
        self.config_path = Path.home() / '.axiom' / 'mcp_services.json'
        self.servers = {}
        self.active_tools = []
        self._sse_clients = {}
        self._pending_requests = {}
        self._request_id_counter = 1000
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        self._ensure_config()
        self.load_servers()

    def _run_loop(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        asyncio.set_event_loop(self._loop)
        self._loop.run_forever()

    def stop(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        for client in self._sse_clients.values():
            self._loop.call_soon_threadsafe(client.stop)
        self._loop.call_soon_threadsafe(self._loop.stop)

    def _ensure_config(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        if not self.config_path.exists():
            self.config_path.write_text(json.dumps({'mcpServers': {}}, indent=2))

    def load_servers(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        try:
            config = json.loads(self.config_path.read_text())
            for name, cfg in config.get('mcpServers', {}).items():
                if name not in self.servers:
                    if 'url' in cfg:
                        self.connect_sse(name, cfg['url'])
                    elif 'command' in cfg:
                        self.connect_stdio(name, cfg['command'], cfg.get('args', []))
        except Exception as e:
            logger.error(f'Failed to load MCP config: {e}')

    def add_server(self, name: str, command: str, args: list):
        """Auto-generated docstring.

Args:
    name: Argument.
    command: Argument.
    args: Argument.

Returns:
    Return value.
"""
        try:
            config = json.loads(self.config_path.read_text())
            if 'mcpServers' not in config:
                config['mcpServers'] = {}
            if command.startswith('http://') or command.startswith('https://'):
                config['mcpServers'][name] = {'url': command}
                self.config_path.write_text(json.dumps(config, indent=2))
                self.connect_sse(name, command)
            else:
                config['mcpServers'][name] = {'command': command, 'args': args}
                self.config_path.write_text(json.dumps(config, indent=2))
                self.connect_stdio(name, command, args)
            return True
        except Exception as e:
            logger.error(f'Failed to add MCP server {name}: {e}')
            return False

    def get_status(self) -> Dict[str, Any]:
        """Auto-generated docstring.


Returns:
    Return value.
"""
        server_info = []
        for name, instance in self.servers.items():
            if isinstance(instance, subprocess.Popen):
                server_info.append({'name': name, 'type': 'STDIO', 'status': 'ONLINE' if instance.poll() is None else 'OFFLINE'})
            else:
                server_info.append({'name': name, 'type': 'SSE', 'status': 'ONLINE' if instance._running else 'OFFLINE'})
        return {'connected_servers': server_info, 'bridged_tools_count': len(self.active_tools)}

    def _next_id(self):
        """Auto-generated docstring.


Returns:
    Return value.
"""
        self._request_id_counter += 1
        return self._request_id_counter

    def _register_future(self, req_id):
        """Auto-generated docstring.

Args:
    req_id: Argument.

Returns:
    Return value.
"""
        future: concurrent.futures.Future[Dict[str, Any]] = concurrent.futures.Future()
        self._pending_requests[req_id] = future
        return future

    def _handle_sse_message(self, name: str, payload: dict):
        """Auto-generated docstring.

Args:
    name: Argument.
    payload: Argument.

Returns:
    Return value.
"""
        req_id = payload.get('id')
        if req_id in self._pending_requests:
            future = self._pending_requests.pop(req_id)
            if not future.done():
                future.set_result(payload)
        elif 'method' in payload:
            logger.debug(f'Received notification from {name}: {payload}')

    def connect_sse(self, name: str, url: str):
        """Auto-generated docstring.

Args:
    name: Argument.
    url: Argument.

Returns:
    Return value.
"""
        try:

            def on_message(payload):
                """Auto-generated docstring.

Args:
    payload: Argument.

Returns:
    Return value.
"""
                self._handle_sse_message(name, payload)

            def on_disconnect():
                """Auto-generated docstring.


Returns:
    Return value.
"""
                if name in self.servers:
                    del self.servers[name]
            client = MCPSSEClient(url, name, on_message, on_disconnect)
            self.servers[name] = client
            self._sse_clients[name] = client
            future: concurrent.futures.Future[bool] = concurrent.futures.Future()

            async def _init_client():
                """Auto-generated docstring.


Returns:
    Return value.
"""
                try:
                    await client.connect()
                    init_req = {'jsonrpc': '2.0', 'id': self._next_id(), 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'axiom', 'version': '2.0'}}}
                    init_future = self._register_future(init_req['id'])
                    await client.send_request(init_req)
                    await asyncio.wrap_future(init_future)
                    await client.send_request({'jsonrpc': '2.0', 'method': 'notifications/initialized'})
                    list_req = {'jsonrpc': '2.0', 'id': self._next_id(), 'method': 'tools/list'}
                    list_future = self._register_future(list_req['id'])
                    await client.send_request(list_req)
                    tools_resp = await asyncio.wrap_future(list_future)
                    tools = tools_resp.get('result', {}).get('tools', [])
                    for t in tools:
                        self._register_mcp_tool_sse(name, t, client)
                    future.set_result(True)
                except Exception as e:
                    import httpx
                    if isinstance(e, (httpx.ConnectError, httpx.TimeoutException, asyncio.TimeoutError)):
                        logger.debug(f'Failed to initialize SSE client {name} (Unreachable): {e}')
                    else:
                        logger.debug(f'Failed to initialize SSE client {name}: {e}')
                    future.set_exception(e)
            asyncio.run_coroutine_threadsafe(_init_client(), self._loop)
            future.result(timeout=10.0)
            logger.info(f"Connected to MCP server '{name}' via SSE.")
        except Exception as e:
            import httpx
            if isinstance(e, (httpx.ConnectError, httpx.TimeoutException, concurrent.futures.TimeoutError)):
                logger.warning(f"Skipping MCP SSE server '{name}' (Unreachable): {e}")
            else:
                logger.warning(f"Failed to start MCP SSE server '{name}': {e}")
            if name in self.servers:
                del self.servers[name]
            if name in self._sse_clients:
                del self._sse_clients[name]

    def _register_mcp_tool_sse(self, server_name: str, tool_def: dict, client: MCPSSEClient):
        """Auto-generated docstring.

Args:
    server_name: Argument.
    tool_def: Argument.
    client: Argument.

Returns:
    Return value.
"""
        tool_name = tool_def.get('name')
        description = tool_def.get('description', '')
        input_schema = tool_def.get('inputSchema', {})
        props = input_schema.get('properties', {})
        req = input_schema.get('required', [])
        schema_params = []
        for k, v in props.items():
            schema_params.append({'name': k, 'type': v.get('type', 'string'), 'description': v.get('description', ''), 'required': k in req})

        class DynamicMCPToolSSE:
            """Auto-generated docstring.

"""
            tool_id = f'{server_name}_{tool_name}'

            def __init__(self, hub):
                """Auto-generated docstring.

Args:
    hub: Argument.

Returns:
    Return value.
"""
                self.hub = hub
                self.description = f'[{server_name} MCP] {description}'
                self.schema = schema_params
                self.execution_count = 0

            def get_info(self):
                """Auto-generated docstring.


Returns:
    Return value.
"""
                return {'name': self.tool_id, 'description': self.description, 'execution_count': self.execution_count, 'parameters': self.schema}

            def execute(self, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
                """Auto-generated docstring.


Returns:
    Return value.
"""
                self.execution_count += 1
                req_id = self.hub._next_id()
                req = {'jsonrpc': '2.0', 'id': req_id, 'method': 'tools/call', 'params': {'name': tool_name, 'arguments': kwargs}}
                future = self.hub._register_future(req_id)

                async def _send():
                    """Auto-generated docstring.


Returns:
    Return value.
"""
                    try:
                        await client.send_request(req)
                    except Exception as e:
                        if not future.done():
                            future.set_exception(e)
                asyncio.run_coroutine_threadsafe(_send(), self.hub._loop)
                try:
                    resp = future.result(timeout=30.0)
                    if 'error' in resp:
                        return {'success': False, 'error': resp['error']}
                    content = resp.get('result', {}).get('content', [])
                    text = ' '.join([c.get('text', '') for c in content if c.get('type') == 'text'])
                    return {'success': True, 'output': text}
                except concurrent.futures.TimeoutError:
                    return {'success': False, 'error': 'Timeout waiting for SSE MCP response'}
                except Exception as e:
                    return {'success': False, 'error': str(e)}
        mcp_tool = DynamicMCPToolSSE(self)
        if hasattr(self.registry, 'register_tool'):
            self.registry.register_tool(mcp_tool.tool_id, mcp_tool)
        elif hasattr(self.registry, 'add_tool'):
            self.registry.add_tool(mcp_tool)
        self.active_tools.append(mcp_tool.tool_id)
        logger.info(f'Registered MCP tool: {mcp_tool.tool_id}')

    def connect_stdio(self, name: str, command: str, args: list):
        """Auto-generated docstring.

Args:
    name: Argument.
    command: Argument.
    args: Argument.

Returns:
    Return value.
"""
        try:
            process = subprocess.Popen([command] + args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
            assert process.stdin is not None
            assert process.stdout is not None
            self.servers[name] = process
            logger.info(f"Connected to MCP server '{name}' via stdio.")
            init_req = {'jsonrpc': '2.0', 'id': 1, 'method': 'initialize', 'params': {'protocolVersion': '2024-11-05', 'capabilities': {}, 'clientInfo': {'name': 'axiom', 'version': '2.0'}}}
            process.stdin.write(json.dumps(init_req) + '\n')
            process.stdin.flush()
            init_resp = process.stdout.readline()
            process.stdin.write(json.dumps({'jsonrpc': '2.0', 'method': 'notifications/initialized'}) + '\n')
            process.stdin.flush()
            req = {'jsonrpc': '2.0', 'id': 2, 'method': 'tools/list'}
            process.stdin.write(json.dumps(req) + '\n')
            process.stdin.flush()
            resp_line = process.stdout.readline()
            if resp_line:
                resp = json.loads(resp_line)
                tools = resp.get('result', {}).get('tools', [])
                for t in tools:
                    self._register_mcp_tool(name, t, process)
        except Exception as e:
            logger.error(f"Failed to start MCP server '{name}': {e}")

    def _register_mcp_tool(self, server_name: str, tool_def: dict, process: subprocess.Popen):
        """Auto-generated docstring.

Args:
    server_name: Argument.
    tool_def: Argument.
    process: Argument.

Returns:
    Return value.
"""
        tool_name = tool_def.get('name')
        description = tool_def.get('description', '')
        input_schema = tool_def.get('inputSchema', {})
        props = input_schema.get('properties', {})
        req = input_schema.get('required', [])
        schema_params = []
        for k, v in props.items():
            schema_params.append({'name': k, 'type': v.get('type', 'string'), 'description': v.get('description', ''), 'required': k in req})

        class DynamicMCPTool:
            """Auto-generated docstring.

"""
            tool_id = f'{server_name}_{tool_name}'

            def __init__(self):
                """Auto-generated docstring.


Returns:
    Return value.
"""
                self.description = f'[{server_name} MCP] {description}'
                self.schema = schema_params
                self.execution_count = 0

            def get_info(self):
                """Auto-generated docstring.


Returns:
    Return value.
"""
                return {'name': self.tool_id, 'description': self.description, 'execution_count': self.execution_count, 'parameters': self.schema}

            def execute(self, **kwargs) -> Dict[str, Any]:  # type: ignore[override]
                """Auto-generated docstring.


Returns:
    Return value.
"""
                self.execution_count += 1
                req_id = 999
                req = {'jsonrpc': '2.0', 'id': req_id, 'method': 'tools/call', 'params': {'name': tool_name, 'arguments': kwargs}}
                try:
                    assert process.stdin is not None
                    assert process.stdout is not None
                    process.stdin.write(json.dumps(req) + '\n')
                    process.stdin.flush()
                    resp_line = process.stdout.readline()
                    if resp_line:
                        resp = json.loads(resp_line)
                        if 'error' in resp:
                            return {'success': False, 'error': resp['error']}
                        content = resp.get('result', {}).get('content', [])
                        text = ' '.join([c.get('text', '') for c in content if c.get('type') == 'text'])
                        return {'success': True, 'output': text}
                except Exception as e:
                    return {'success': False, 'error': str(e)}
                return {'success': False, 'error': 'No response from MCP server'}
        mcp_tool = DynamicMCPTool()
        if hasattr(self.registry, 'register_tool'):
            self.registry.register_tool(mcp_tool.tool_id, mcp_tool)
        elif hasattr(self.registry, 'add_tool'):
            self.registry.add_tool(mcp_tool)
        self.active_tools.append(mcp_tool.tool_id)
        logger.info(f'Registered MCP tool: {mcp_tool.tool_id}')
