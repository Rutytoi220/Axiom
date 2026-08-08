import sys

with open("axiom/engine/router.py", "r") as f:
    text = f.read()

# Replace _async_get_installed_models
old_fetch = """    async def _async_get_installed_models(self) -> List[str]:
        \"\"\"Fetch current installed models from Ollama asynchronously.\"\"\"
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get('http://localhost:11434/api/tags', timeout=2.0)
                if r.status_code == 200:
                    return [m['name'] for m in r.json().get('models', [])]
        except Exception as e:
            logger.warning(f"[SmartRouter] Failed to fetch installed models: {e}")
        return []"""

new_fetch = """    async def _async_get_installed_models(self) -> List[str]:
        \"\"\"Fetch current installed models from Ollama asynchronously.\"\"\"
        if getattr(self, '_ollama_offline', False):
            return []
        try:
            async with httpx.AsyncClient() as client:
                r = await client.get('http://127.0.0.1:11434/api/tags', timeout=3.0)
                if r.status_code == 200:
                    return [m['name'] for m in r.json().get('models', [])]
        except Exception:
            self._ollama_offline = True
            logger.error("ERROR: Ollama daemon not found at 127.0.0.1:11434")
        return []"""

text = text.replace(old_fetch, new_fetch)

# Replace _resolve_dynamic_tiers
old_resolve = """    def _resolve_dynamic_tiers(self) -> Dict[IntentCategory, str]:
        \"\"\"Dynamically select the best installed models for each tier.\"\"\"
        default_tiers = {
            IntentCategory.CHAT: 'ollama/llama3.1:latest', 
            IntentCategory.SYSTEM: 'ollama/qwen2.5-coder:7b', 
            IntentCategory.CODE: 'ollama/qwen2.5-coder:latest', 
            IntentCategory.VISION: 'ollama/qwen3-vl:2b', 
            IntentCategory.REASONING: 'ollama/laguna-xs-2.1:q4_K_M'
        }
        models = self._get_installed_models()
        if not models:
            return default_tiers

        def pick_best(keywords: List[str], fallback: str) -> str:
            for kw in keywords:
                for m in models:
                    if kw.lower() in m.lower():
                        return f"ollama/{m}"
            return f"ollama/{models[0]}" if models else fallback

        return {
            IntentCategory.CODE: pick_best(['laguna', 'coder', 'deepseek', 'qwen', 'llama'], default_tiers[IntentCategory.CODE]),
            IntentCategory.CHAT: pick_best(['llama', 'mistral', 'gemma', 'qwen', 'laguna'], default_tiers[IntentCategory.CHAT]),
            IntentCategory.VISION: pick_best(['vl', 'llava', 'vision', 'pixtral'], default_tiers[IntentCategory.VISION]),
            IntentCategory.REASONING: pick_best(['r1', 'reason', 'math', 'laguna', 'deepseek'], default_tiers[IntentCategory.REASONING]),
            IntentCategory.SYSTEM: pick_best(['coder', 'qwen', 'llama', 'mistral', 'laguna'], default_tiers[IntentCategory.SYSTEM])
        }"""

new_resolve = """    def _resolve_dynamic_tiers(self) -> Dict[IntentCategory, str]:
        \"\"\"Dynamically select the best installed models for each tier.\"\"\"
        models = self._get_installed_models()
        if not models:
            return {}

        def pick_best(keywords: List[str]) -> str:
            for kw in keywords:
                for m in models:
                    if kw.lower() in m.lower():
                        return f"ollama/{m}"
            return f"ollama/{models[0]}" if models else ""

        # Router/Chat: Smallest/fastest model (often has '1.5b', '2b', '0.5b', '3b' in name)
        # Orchestrator (System/Reasoning/Code): Largest/most capable
        
        # We will parse parameter sizes if possible, but fallback to heuristics
        small_kws = ['0.5b', '1.5b', '2b', '3b', 'functiongemma', 'qwen3:0.6b', 'smollm']
        large_kws = ['32b', '70b', 'r1', 'deepseek', 'laguna', 'coder', 'qwen2.5', 'llama3']
        
        return {
            IntentCategory.CODE: pick_best(large_kws + ['coder', 'qwen']),
            IntentCategory.CHAT: pick_best(small_kws + ['llama', 'gemma', 'qwen']),
            IntentCategory.VISION: pick_best(['vl', 'llava', 'vision', 'pixtral']),
            IntentCategory.REASONING: pick_best(large_kws + ['reason', 'math']),
            IntentCategory.SYSTEM: pick_best(large_kws + ['coder', 'qwen'])
        }"""

text = text.replace(old_resolve, new_resolve)

with open("axiom/engine/router.py", "w") as f:
    f.write(text)
