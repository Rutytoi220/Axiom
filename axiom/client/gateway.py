import asyncio
import json
import logging
import psutil
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Depends, HTTPException, Header, Query, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)

class MacroStopRequest(BaseModel):
    name: str

def create_app(daemon) -> FastAPI:
    app = FastAPI(title="AXIOM Local Gateway")
    
    # Add CORS middleware for the React Vite dev server
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    app.state.daemon = daemon

    gui_dir = Path.home() / ".axiom" / "gui"
    gui_dir.mkdir(parents=True, exist_ok=True)
    index_file = gui_dir / "index.html"
    if not index_file.exists() or index_file.stat().st_size == 0:
        fallback_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AXIOM Gateway</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 100%);
            color: #f8fafc;
            display: flex;
            align-items: center;
            justify-content: center;
            height: 100vh;
        }
        .container {
            background: rgba(255, 255, 255, 0.05);
            backdrop-filter: blur(16px);
            -webkit-backdrop-filter: blur(16px);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: 24px;
            padding: 48px;
            max-width: 600px;
            text-align: center;
            box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.5);
            animation: float 6s ease-in-out infinite;
        }
        @keyframes float {
            0% { transform: translateY(0px); }
            50% { transform: translateY(-10px); }
            100% { transform: translateY(0px); }
        }
        h1 {
            font-size: 2.5rem;
            margin-bottom: 16px;
            background: linear-gradient(to right, #38bdf8, #818cf8);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }
        p {
            font-size: 1.125rem;
            line-height: 1.6;
            color: #94a3b8;
            margin-bottom: 32px;
        }
        .code-block {
            background: rgba(0, 0, 0, 0.4);
            border-radius: 8px;
            padding: 16px;
            font-family: monospace;
            color: #34d399;
            text-align: left;
            overflow-x: auto;
            border: 1px solid rgba(255, 255, 255, 0.05);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>AXIOM GUI Sandbox</h1>
        <p>The backend daemon is running securely, but no frontend assets were found.</p>
        <p>To deploy the React GUI payload, build your frontend and copy it to the asset directory:</p>
        <div class="code-block">
npm run build<br>
cp -r dist/* ~/.axiom/gui/
        </div>
    </div>
</body>
</html>"""
        index_file.write_text(fallback_html, encoding="utf-8")

    async def verify_token(
        request: Request,
        authorization: Optional[str] = Header(None),
        token: Optional[str] = Query(None)
    ):
        expected = daemon.token
        if authorization and authorization.startswith("Bearer "):
            provided = authorization[7:]
        elif token:
            provided = token
        else:
            raise HTTPException(status_code=401, detail="Unauthorized")
        
        if provided != expected:
            raise HTTPException(status_code=401, detail="Invalid token")
        return provided

    @app.get("/api/status")
    async def get_status(token: Optional[str] = Query(None)):
        # Optional: We bypass token verification for status if running locally so the frontend can hit it easily without complex auth sync.
        # If strict auth is required, we can keep the verify_token dependency.
        engine = daemon.engine
        mem = psutil.virtual_memory()
        cpu = psutil.cpu_percent(interval=0.1)
        
        engine_running = False
        if hasattr(engine, "is_running"):
            engine_running = engine.is_running()
        elif hasattr(engine, "_running"):
            engine_running = engine._running
            
        agents = len(engine.registry.list_agents()) if hasattr(engine, "registry") and hasattr(engine.registry, "list_agents") else 0
        tools = len(engine.registry.list_tools()) if hasattr(engine, "registry") and hasattr(engine.registry, "list_tools") else 0
        plugins = len(engine.registry.list_plugins()) if hasattr(engine, "registry") and hasattr(engine.registry, "list_plugins") else 0
        
        
        model_name = "Unknown"
        if hasattr(daemon, "ollama") and hasattr(daemon.ollama, "config"):
            model_name = daemon.ollama.config.model
            
        return {
            "engine_running": engine_running,
            "ram_percent": mem.percent,
            "cpu_percent": cpu,
            "agents": agents,
            "tools": tools,
            "plugins": plugins,
            "model": model_name
        }

    @app.post("/api/macros/start")
    async def start_macro(token: str = Depends(verify_token)):
        plugin = daemon.engine.registry.get_plugin("automation")
        if not plugin:
            raise HTTPException(status_code=404, detail="Automation plugin not found")
        plugin.start_recording()
        return {"status": "recording_started"}

    @app.post("/api/macros/stop")
    async def stop_macro(req: MacroStopRequest, token: str = Depends(verify_token)):
        plugin = daemon.engine.registry.get_plugin("automation")
        if not plugin:
            raise HTTPException(status_code=404, detail="Automation plugin not found")
        macro_id = plugin.stop_recording(req.name)
        if not macro_id:
            raise HTTPException(status_code=400, detail="No steps recorded")
        return {"status": "recording_stopped", "macro_id": macro_id}

    @app.get("/api/macros")
    async def get_macros(token: Optional[str] = Query(None)): 
        # Open locally for easy dashboard access
        plugin = daemon.engine.registry.get_plugin("automation")
        if not plugin:
            raise HTTPException(status_code=404, detail="Automation plugin not found")
        return {"macros": plugin.list_macros()}

    @app.post("/api/macros/{macro_id}/execute")
    async def execute_macro(macro_id: str, token: str = Depends(verify_token)):
        plugin = daemon.engine.registry.get_plugin("automation")
        if not plugin:
            raise HTTPException(status_code=404, detail="Automation plugin not found")
        success = plugin.execute_macro(macro_id)
        if not success:
            raise HTTPException(status_code=400, detail="Failed to execute macro")
        return {"status": "executing"}

    @app.delete("/api/macros/{macro_id}")
    async def delete_macro(macro_id: str, token: str = Depends(verify_token)):
        plugin = daemon.engine.registry.get_plugin("automation")
        if not plugin:
            raise HTTPException(status_code=404, detail="Automation plugin not found")
        success = plugin.delete_macro(macro_id)
        if not success:
            raise HTTPException(status_code=404, detail="Macro not found")
        return {"status": "deleted"}

    @app.websocket("/ws/events")
    async def websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
        client_host = websocket.client.host if websocket.client else ""
        is_local = client_host in ("127.0.0.1", "localhost", "::1")
        
        expected = daemon.token
        if not is_local and token != expected:
            await websocket.close(code=1008) # Policy Violation
            return

        await websocket.accept()
        queue = asyncio.Queue()
        loop = asyncio.get_running_loop()

        def event_handler(event):
            name = getattr(event, "name", getattr(event, "event_type", "unknown"))
            payload = getattr(event, "payload", getattr(event, "data", None))
            msg = {
                "jsonrpc": "2.0",
                "method": "axiom.event",
                "params": {
                    "event_type": name,
                    "payload": payload
                }
            }
            try:
                loop.call_soon_threadsafe(queue.put_nowait, json.dumps(msg, default=str))
            except Exception:
                pass

        bus = getattr(daemon.engine, "event_bus", None)
        if bus and hasattr(bus, "subscribe"):
            bus.subscribe("*", event_handler)

        try:
            while True:
                msg = await queue.get()
                await websocket.send_text(msg)
        except WebSocketDisconnect:
            pass
        finally:
            if bus and hasattr(bus, "unsubscribe"):
                bus.unsubscribe("*", event_handler)

    app.mount("/", StaticFiles(directory=str(gui_dir), html=True), name="gui")

    return app
