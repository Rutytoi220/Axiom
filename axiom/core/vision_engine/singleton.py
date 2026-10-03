import threading

_engine_instance = None
_engine_lock = threading.Lock()

def get_grounding_engine():
    global _engine_instance
    with _engine_lock:
        if _engine_instance is None:
            print(">>> [AXIOM] Bootstrapping resident AxiomGroundingEngine into CUDA memory...")
            from axiom.core.vision_engine.axiom_engine import AxiomGroundingEngine
            _engine_instance = AxiomGroundingEngine()
    return _engine_instance
