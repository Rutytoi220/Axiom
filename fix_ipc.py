with open('axiom/core/ipc_server.py', 'r') as f:
    c = f.read()

c = c.replace('import websockets', 'import websockets\nimport websockets.server\nimport websockets.exceptions')
c = c.replace('self.authenticated_clients: Set[websockets.WebSocketServerProtocol] = set()', 'self.authenticated_clients: Set[websockets.server.WebSocketServerProtocol] = set()')
c = c.replace('self.subscribers: Dict[websockets.WebSocketServerProtocol, Set[str]] = {}', 'self.subscribers: Dict[websockets.server.WebSocketServerProtocol, Set[str]] = {}')
c = c.replace('self._ws_server = None', 'self._ws_server: websockets.server.Serve | None = None')
c = c.replace('self._uds_server = None', 'self._uds_server: asyncio.Server | None = None')
c = c.replace('self._http_server = None', 'self._http_server: Any | None = None')
c = c.replace('self._http_task = None', 'self._http_task: asyncio.Task[Any] | None = None')

with open('axiom/core/ipc_server.py', 'w') as f:
    f.write(c)
