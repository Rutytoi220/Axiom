import re

with open('tests/test_persona.py', 'r') as f:
    content = f.read()

new_tests = """import pytest
from axiom.core.persona import PersonaConfig, PersonaCompiler

def test_persona_compiler_deterministic():
    config1 = PersonaConfig(
        identity={"name": "Alpha", "role": "Test Agent"},
        communication={
            "tone": "strict", "verbosity": "concise", 
            "technical_depth": "developer", "formatting_preference": "heavy_code"
        },
        behavior={
            "provide_confidence_percentage": True, 
            "explain_dangerous_commands": False, 
            "use_emojis": True,
            "initiative": "proactive",
            "confirmation_policy": "auto_execute",
            "show_inner_monologue": True
        },
        directives=["Do not hallucinate.", "Stay focused."]
    )
    
    config2 = PersonaConfig(
        identity={"name": "Alpha", "role": "Test Agent"},
        communication={
            "tone": "strict", "verbosity": "concise", 
            "technical_depth": "developer", "formatting_preference": "heavy_code"
        },
        behavior={
            "provide_confidence_percentage": True, 
            "explain_dangerous_commands": False, 
            "use_emojis": True,
            "initiative": "proactive",
            "confirmation_policy": "auto_execute",
            "show_inner_monologue": True
        },
        directives=["Do not hallucinate.", "Stay focused."]
    )
    
    result1 = PersonaCompiler.compile(config1)
    result2 = PersonaCompiler.compile(config2)
    
    assert result1 == result2
    assert "Alpha" in result1
    assert "Test Agent" in result1
    assert "**Technical Depth:** developer" in result1
    assert "**Formatting:** heavy_code" in result1
    assert "[COGNITION: ENABLED]" in result1
    assert "[INITIATIVE: PROACTIVE]" in result1
    assert "[CONFIRMATION: AUTO-EXECUTE]" in result1
    assert "[ENABLED] Always provide a confidence percentage" in result1
    assert "[DISABLED] Do not explain dangerous commands" in result1
    assert "[ENABLED] Use emojis" in result1

def test_persona_compiler_directives():
    config = PersonaConfig(directives=["Directive A", "Directive B"])
    result = PersonaCompiler.compile(config)
    
    assert "1. Directive A" in result
    assert "2. Directive B" in result
"""

with open('tests/test_persona.py', 'w') as f:
    f.write(new_tests)
