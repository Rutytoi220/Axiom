import re

with open('axiom/config.py', 'r') as f:
    content = f.read()

# Add persona dict field
content = re.sub(r'    persona_tone: str = \'balanced\'\n    persona_complexity: str = \'standard\'\n    special_instructions: str = \'\'\n    llm_complexity: str = \'detailed\' # \'concise\', \'detailed\', \'academic\'', '    persona: dict = field(default_factory=dict)\n    llm_complexity: str = \'detailed\'', content)

# Remove from to_dict
content = re.sub(r'            \'persona_tone\': self\.persona_tone,\n            \'persona_complexity\': self\.persona_complexity,\n            \'special_instructions\': self\.special_instructions,\n', '            \'persona\': self.persona,\n', content)

# Remove from from_dict (filtered implicitly handles dict keys so it will pick up persona, but wait, from_dict handles mapping legacy keys to persona?)
def transform_from_dict(match):
    return """        filtered = {k: v for k, v in config_dict.items() if k in cls.__dataclass_fields__}
        
        # Migrate legacy loose persona strings to new dict structure
        if 'persona' not in filtered:
            filtered['persona'] = {}
            if 'persona_tone' in config_dict:
                filtered['persona']['communication'] = {'tone': config_dict['persona_tone'], 'verbosity': config_dict.get('persona_complexity', 'standard')}
            if 'special_instructions' in config_dict and config_dict['special_instructions']:
                filtered['persona']['directives'] = [config_dict['special_instructions']]
                
        if 'auth_mode' in filtered and isinstance(filtered['auth_mode'], str):"""

content = re.sub(r'        filtered = \{k: v for k, v in config_dict\.items\(\) if k in cls\.__dataclass_fields__\}\n        if \'auth_mode\' in filtered and isinstance\(filtered\[\'auth_mode\'\], str\):', transform_from_dict, content)

with open('axiom/config.py', 'w') as f:
    f.write(content)
