import pytest
import os
import tempfile
import json
import csv
from axiom.tools.document_reader import ReadDocumentContentTool

@pytest.fixture
def temp_dir():
    with tempfile.TemporaryDirectory() as d:
        yield d

@pytest.mark.asyncio
async def test_read_plain_text(temp_dir):
    tool = ReadDocumentContentTool()
    file_path = os.path.join(temp_dir, "test.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write("Hello AXIOM.")
        
    result = await tool.execute({"file_path": file_path})
    assert result.success is True
    assert result.output["content"] == "Hello AXIOM."

@pytest.mark.asyncio
async def test_read_json(temp_dir):
    tool = ReadDocumentContentTool()
    file_path = os.path.join(temp_dir, "test.json")
    data = {"key": "value"}
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(data, f)
        
    result = await tool.execute({"file_path": file_path})
    assert result.success is True
    assert '"key": "value"' in result.output["content"]

@pytest.mark.asyncio
async def test_read_csv(temp_dir):
    tool = ReadDocumentContentTool()
    file_path = os.path.join(temp_dir, "test.csv")
    with open(file_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Name", "Age"])
        writer.writerow(["Alice", "30"])
        
    result = await tool.execute({"file_path": file_path})
    assert result.success is True
    assert "Name, Age\nAlice, 30" in result.output["content"]

@pytest.mark.asyncio
async def test_read_binary_fallback(temp_dir):
    tool = ReadDocumentContentTool()
    file_path = os.path.join(temp_dir, "test.pdf")
    
    # Create a dummy binary file with some text embedded
    with open(file_path, "wb") as f:
        f.write(b"\x00\x01\x02\x03")
        f.write(b"Hello from PDF. This is a longer string.")
        f.write(b"\x00\x04\x05")
        
    result = await tool.execute({"file_path": file_path})
    assert result.success is True
    assert "Hello from PDF" in result.output["content"]

@pytest.mark.asyncio
async def test_empty_or_scanned_pdf_safeguard(temp_dir):
    tool = ReadDocumentContentTool()
    file_path = os.path.join(temp_dir, "scanned.pdf")
    
    # Create a dummy pdf that only yields 5 alphanumeric characters
    with open(file_path, "wb") as f:
        f.write(b"\x00\x01\x02\x03")
        f.write(b"Short")
        f.write(b"\x00\x04\x05")
        
    result = await tool.execute({"file_path": file_path})
    assert result.success is False
    assert "Could not extract readable text" in result.error
    assert "scanned image" in result.error

@pytest.mark.asyncio
async def test_truncation(temp_dir):
    tool = ReadDocumentContentTool()
    file_path = os.path.join(temp_dir, "large.txt")
    
    # Create a 15KB file
    content = "A" * 15000
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(content)
        
    result = await tool.execute({"file_path": file_path})
    assert result.success is True
    extracted = result.output["content"]
    
    assert len(extracted) > 10000
    assert len(extracted) < 15000
    assert "[... TRUNCATED TO 10KB FOR SAFETY ...]" in extracted
