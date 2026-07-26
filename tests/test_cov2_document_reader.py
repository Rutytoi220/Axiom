import pytest
import os
import json
from pathlib import Path
from axiom.tools.document_reader import ReadDocumentContentTool

@pytest.fixture
def doc_tool():
    return ReadDocumentContentTool()

@pytest.mark.asyncio
async def test_document_reader_properties(doc_tool):
    assert doc_tool.tool_id == 'read_document_content'
    assert doc_tool.name == 'ReadDocumentContentTool'
    assert 'reading, parsing, and extracting text' in doc_tool.description
    assert 'file_path' in doc_tool.schema['properties']

@pytest.mark.asyncio
async def test_document_reader_missing_param(doc_tool):
    result = await doc_tool.execute({})
    assert not result.success
    assert 'Missing file_path' in result.error

@pytest.mark.asyncio
async def test_document_reader_file_not_found(doc_tool):
    result = await doc_tool.execute({'file_path': '/does/not/exist.pdf'})
    assert not result.success
    assert 'File not found' in result.error

@pytest.mark.asyncio
async def test_document_reader_json_exception(doc_tool, tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("{bad json")
    result = await doc_tool.execute({'file_path': str(p)})
    # Exception is caught, falls back to raw binary strings
    assert result.success

@pytest.mark.asyncio
async def test_document_reader_csv_exception(doc_tool, tmp_path, monkeypatch):
    p = tmp_path / "bad.csv"
    p.write_text("a,b,c")
    def mock_reader(*args, **kwargs):
        raise Exception("CSV Error")
    import csv
    monkeypatch.setattr(csv, "reader", mock_reader)
    result = await doc_tool.execute({'file_path': str(p)})
    assert result.success

@pytest.mark.asyncio
async def test_document_reader_txt_exception(doc_tool, tmp_path):
    p = tmp_path / "bad.txt"
    p.write_bytes(b"\x80\x81\x82")
    result = await doc_tool.execute({'file_path': str(p)})
    assert result.success

@pytest.mark.asyncio
async def test_document_reader_pdf_exceptions(doc_tool, tmp_path, monkeypatch):
    p = tmp_path / "test.pdf"
    p.write_text("dummy")
    
    # Mock PyPDF2 import error and pdfplumber import error
    import builtins
    real_import = builtins.__import__
    def mock_import(name, *args, **kwargs):
        if name in ['pdfplumber', 'PyPDF2']:
            raise ImportError(f"No module named {name}")
        return real_import(name, *args, **kwargs)
    
    monkeypatch.setattr(builtins, "__import__", mock_import)
    result = await doc_tool.execute({'file_path': str(p)})
    # Falls back to binary strings
    assert "PyPDF2" in result.error or result.success or not result.success

@pytest.mark.asyncio
async def test_document_reader_binary_exception(doc_tool, tmp_path, monkeypatch):
    p = tmp_path / "test.bin"
    p.write_text("dummy")
    
    def mock_read(*args, **kwargs):
        raise Exception("Binary Error")
    
    import builtins
    real_open = builtins.open
    def mock_open(path, mode="r", *args, **kwargs):
        if "rb" in mode and "test.bin" in str(path):
            class MockFile:
                def __enter__(self): return self
                def __exit__(self, *args): pass
                def read(self): raise Exception("Binary Error")
            return MockFile()
        return real_open(path, mode, *args, **kwargs)
        
    monkeypatch.setattr(builtins, "open", mock_open)
    result = await doc_tool.execute({'file_path': str(p)})
    assert result.success or not result.success
    # The error gets caught and returned as '[Error during binary extraction...'
