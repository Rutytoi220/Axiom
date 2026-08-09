import logging
import json
import asyncio
from pathlib import Path
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

from axiom.config import get_config
from axiom.core import Engine
from axiom.memory import SyncMemoryStore
from axiom.llm.universal_client import UniversalLLMClient
from axiom.agents.orchestrator_agent import OrchestratorAgent
from axiom.tool_registry import ToolRegistry
from axiom.tools.plugin_loader import load_plugins
from axiom.core.config_service import initialize_model_config
from axiom.tools import EchoTool, ShellTool, FileReadTool, FileWriteTool, SystemInfoTool
from axiom.legacy_wrapper import create_legacy_tools

logger = logging.getLogger("axiom.node")
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

app = FastAPI(title="AXIOM Node API", description="Headless Distributed Swarm Node")

class NodeState:
    def __init__(self):
        self.engine = None
        self.memory = None
        self.ollama = None
        self.orchestrator = None

state = NodeState()

@app.on_event("startup")
async def startup_event():
    logger.info("Initializing AXIOM Headless Engine...")
    
    config = get_config()
    state.ollama = UniversalLLMClient(default_model=config.ollama_model)
    initialize_model_config(config, state.ollama)
    
    # Setup Memory
    axiom_dir = Path.home() / '.axiom'
    axiom_dir.mkdir(exist_ok=True, parents=True)
    db_path = str(axiom_dir / 'axiom.db')
    state.memory = SyncMemoryStore(db_path, embedding_provider=state.ollama)
    
    # Engine & Registry
    state.engine = Engine(memory=state.memory)
    state.engine.initialize()
    
    tool_registry = ToolRegistry(state.engine.registry)
    
    # Load default tools
    tools = [
        EchoTool(), ShellTool(), FileReadTool('.'), FileWriteTool('.'), SystemInfoTool()
    ]
    tools.extend(create_legacy_tools())
    for tool in tools:
        state.engine.registry.register_tool(tool.tool_id, tool)
        
    load_plugins(tool_registry)
    
    # Orchestrator
    state.orchestrator = OrchestratorAgent(
        tool_registry, 
        state.engine.event_bus, 
        state.memory, 
        llm=state.ollama
    )
    state.engine.registry.register_agent(state.orchestrator.name, state.orchestrator)
    state.memory.create_conversation('AXIOM Node Session')
    
    logger.info("AXIOM Headless Engine Online.")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down AXIOM Headless Engine...")
    if state.engine:
        state.engine.shutdown()
    if state.memory:
        state.memory.close()
    if state.ollama:
        state.ollama.close()

@app.websocket("/ws/swarm")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    logger.info("New WebSocket connection accepted on /ws/swarm")
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                prompt = payload.get("prompt", "")
            except json.JSONDecodeError:
                prompt = data
                
            if not prompt:
                continue
                
            logger.info(f"Received prompt: {prompt}")
            
            # Send processing status
            await websocket.send_text(json.dumps({"status": "processing"}))
            
            # Phase 1: Blocking execution run in a separate thread to not block the asyncio event loop
            loop = asyncio.get_running_loop()
            response = await loop.run_in_executor(None, state.orchestrator.run, prompt)
            
            output_str = ""
            if response.output:
                if isinstance(response.output, dict):
                    output_str = response.output.get('response', '')
                elif isinstance(response.output, str):
                    output_str = response.output
                else:
                    output_str = json.dumps(response.output, default=str)
                    
            if not output_str and response.error:
                output_str = f"Error: {response.error}"
                
            import re
            output_str = re.sub(r'<think>[\s\S]*?(?:</think>|$)', '', output_str, flags=re.IGNORECASE)
            output_str = output_str.replace('</think>', '').replace('<think>', '').strip()
                
            # Stream the final result back
            await websocket.send_text(json.dumps({
                "status": "complete",
                "response": output_str
            }))
            
            # Record in memory
            state.memory.add_message('user', prompt)
            state.memory.add_message('assistant', output_str)
            
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}", exc_info=True)
        try:
            await websocket.send_text(json.dumps({"status": "error", "message": str(e)}))
        except:
            pass
