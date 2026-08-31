with open('axiom/gui/widgets/health_radar.py', 'r') as f:
    content = f.read()
    
# Change the vram logic
old_logic = """        vram_pct = data.get("vram_percent", 0.0)
        vram_mb = data.get("vram_mb", 0.0)
        if vram_mb > 0:
            self.vram_bar.set_value(vram_pct, f"{vram_mb:.0f} MB")
        else:
            self.vram_bar.set_value(0, "N/A")"""
            
new_logic = """        vram_pct = data.get("vram_percent", 0.0)
        vram_mb = data.get("vram_mb", 0.0)
        gpu_name = data.get("gpu_name", "Integrated / CPU-Only")
        
        if "Integrated" in gpu_name:
            self.vram_bar.set_value(0, "Shared")
            self.vram_bar.title_lbl.setText("GPU (Integrated)")
        else:
            self.vram_bar.set_value(vram_pct, f"{vram_mb:.0f} MB")
            self.vram_bar.title_lbl.setText(f"VRAM ({gpu_name.split()[0]})")"""
            
content = content.replace(old_logic, new_logic)

with open('axiom/gui/widgets/health_radar.py', 'w') as f:
    f.write(content)
