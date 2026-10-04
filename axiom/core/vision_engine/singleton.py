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
            AxiomGroundingEngine._instance = _engine_instance
    return _engine_instance


def evict_grounding_engine():
    global _engine_instance
    with _engine_lock:
        if _engine_instance is not None:
            print(">>> [AXIOM] Evicting resident AxiomGroundingEngine from CUDA memory...")
            try:
                if hasattr(_engine_instance, "unload"):
                    _engine_instance.unload()
            except Exception as e:
                print(f"Warning during vision engine eviction: {e}")
            _engine_instance = None
            try:
                from axiom.core.vision_engine.axiom_engine import AxiomGroundingEngine
                AxiomGroundingEngine._instance = None
            except Exception:
                pass
            import gc, torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

