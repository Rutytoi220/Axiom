"""Tool for safely reading and extracting text from documents."""

import os
import csv
import json
import re
from typing import Any, Dict
from pathlib import Path

from axiom.tools import BaseTool, ToolResult

class ReadDocumentContentTool(BaseTool):
    """Safely extracts text content from various document formats."""
    
    MAX_CONTEXT_LENGTH = 10000  # 10KB truncation limit

    @property
    def tool_id(self) -> str: return "read_document_content"

    @property
    def name(self) -> str: return "ReadDocumentContentTool"

    @property
    def description(self) -> str:
        return "REQUIRED and EXCLUSIVE tool for reading, parsing, and extracting text from PDF (.pdf), Word (.docx), CSV (.csv), and rich text documents."

    @property
    def schema(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "file_path": {"type": "string", "description": "Absolute path to the file"}
            },
            "required": ["file_path"]
        }

    async def execute(self, params: Dict[str, Any]) -> ToolResult:
        file_path = params.get("file_path")
        if not file_path:
            return ToolResult(success=False, error="Missing file_path")

        path = Path(file_path).resolve()
        if not path.exists() or not path.is_file():
            return ToolResult(success=False, error=f"File not found: {file_path}")

        try:
            content = self._extract_text(path)
            
            # Zero-Token Hallucination Safeguard (only for binary documents)
            if path.suffix.lower() in [".pdf", ".docx", ".doc"]:
                # Ignore fallback error prefixes when counting characters
                raw_content = content
                if "[!] Error:" in content and "Falling back to raw binary string extraction." in content:
                    parts = content.split("Falling back to raw binary string extraction.\n")
                    if len(parts) > 1:
                        raw_content = parts[-1]
                
                alphanumeric_count = sum(c.isalnum() for c in raw_content)
                if alphanumeric_count < 15:
                    return ToolResult(
                        success=False,
                        error=f" [!] Error: Could not extract readable text from {path.name}. This file may be a scanned image lacking a selectable text layer, encrypted, or corrupted. Please convert it with OCR or provide a plain text file."
                    )
                
            truncated_content = self._truncate_safe(content)
            return ToolResult(
                success=True,
                output={
                    "file": path.name,
                    "content": truncated_content
                }
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Failed to extract document: {e}")

    def _extract_text(self, path: Path) -> str:
        ext = path.suffix.lower()
        
        if ext == ".json":
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return json.dumps(data, indent=2)
            except Exception:
                pass # fallback to string extraction
                
        if ext == ".csv":
            try:
                with open(path, "r", encoding="utf-8") as f:
                    reader = csv.reader(f)
                    lines = [", ".join(row) for row in reader]
                return "\n".join(lines)
            except Exception:
                pass # fallback
                
        if ext in [".txt", ".md", ".log", ".py", ".js", ".yaml", ".yml"]:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except UnicodeDecodeError:
                pass # fallback to binary extraction if encoding fails

        if ext == ".pdf":
            extracted_text = ""
            
            # Primary attempt: pdfplumber
            try:
                import pdfplumber
                with pdfplumber.open(path) as pdf:
                    extracted_text = "\n".join((page.extract_text() or "") for page in pdf.pages)
            except ImportError:
                pass
            except Exception:
                pass
                
            if sum(c.isalnum() for c in extracted_text) >= 15:
                return extracted_text

            # Secondary attempt: PyPDF2
            try:
                import PyPDF2
                with open(path, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    text = "\n".join((page.extract_text() or "") for page in reader.pages)
                    if text:
                        return text
            except ImportError:
                return "[!] Error: 'PyPDF2' and 'pdfplumber' are not installed. Please install one of them for robust PDF parsing. Falling back to raw binary string extraction.\n" + self._extract_binary_strings(path)
            except Exception as e:
                pass
                
            # If both failed or returned empty text
            return ""

        # Graceful fallback string extractor for complex/binary documents (.pdf, .docx, or failed utf-8)
        return self._extract_binary_strings(path)

    def _extract_binary_strings(self, path: Path) -> str:
        """Extracts readable ASCII strings from binary files, ignoring headers."""
        try:
            with open(path, "rb") as f:
                data = f.read()
            
            # Find contiguous sequences of 4 or more printable ASCII characters (tab, newline, space to ~)
            # This cleanly extracts text blocks embedded in PDFs and DOCX files without heavy dependencies.
            pattern = re.compile(b'[\\x09\\x0A\\x0D\\x20-\\x7E]{4,}')
            matches = pattern.findall(data)
            
            extracted = "\n".join(match.decode("ascii") for match in matches)
            return extracted.strip()
        except Exception as e:
            return f"[Error during binary extraction: {e}]"

    def _truncate_safe(self, text: str) -> str:
        """Truncates text to MAX_CONTEXT_LENGTH to protect the LLM context window."""
        if len(text) > self.MAX_CONTEXT_LENGTH:
            return text[:self.MAX_CONTEXT_LENGTH] + "\n\n[... TRUNCATED TO 10KB FOR SAFETY ...]"
        return text
