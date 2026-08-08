import re
import html

def basic_markdown_to_html(raw_text: str) -> str:
    safe_text = html.escape(raw_text)
    
    # Pre-process newlines so they don't break regex
    safe_text = re.sub(
        r"```(.*?)```", 
        lambda m: f"<pre style='background-color: #1E1E1E; color: #E0E0E0; padding: 10px; border-radius: 8px; font-family: monospace;'>{m.group(1)}</pre>", 
        safe_text, 
        flags=re.DOTALL
    )
    
    safe_text = re.sub(
        r"`([^`\n]+)`", 
        r"<code style='background-color: #1E1E1E; color: #E0E0E0; padding: 2px 4px; border-radius: 4px; font-family: monospace;'>\1</code>", 
        safe_text
    )
    
    safe_text = re.sub(r"\*\*([^\*]+)\*\*", r"<b>\1</b>", safe_text)
    safe_text = safe_text.replace("\n", "<br>")
    return safe_text

print(basic_markdown_to_html("Hello **world**!\n```python\nprint('hello')\n```\nHere is `inline` code."))
