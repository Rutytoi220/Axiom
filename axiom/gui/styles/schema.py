from pydantic import BaseModel, ConfigDict
from typing import Dict

class ThemeTokens(BaseModel):
    model_config = ConfigDict(extra='allow')
    
    bg_base: str
    bg_surface: str
    primary: str = ""
    accent: str
    text_main: str = ""
    text_muted: str
    borders: str = ""
    
    spacing_sm: str
    spacing_md: str
    radius_sm: str
    radius_md: str
    
    font_main: str
    font_mono: str

class ThemeManifest(BaseModel):
    id: str
    name: str
    author: str
    version: str
    tokens: ThemeTokens
