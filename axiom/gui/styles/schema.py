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
    danger: str = "#ef4444"
    success: str = "#10b981"
    
    spacing_sm: str
    spacing_md: str
    radius_sm: str
    radius_md: str
    radius_lg: str = "12px"
    
    font_main: str
    font_mono: str

class ThemeManifest(BaseModel):
    id: str
    name: str
    author: str
    version: str
    tokens: ThemeTokens
