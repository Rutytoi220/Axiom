from axiom.engine.skill_compiler import SkillCompilerEngine
engine = SkillCompilerEngine()
code = """
def calculate_hash(text):
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()
"""
res = engine.compile_skill("calculate_hash", code, "Calculates MD5 hash")
print("Compile success:", res)

tool = engine.registry.get_tool("calculate_hash")
print("Registered Tool:", tool)
if tool:
    res = tool.execute({"input": "axiom"})
    print("Execution Result:", res)
