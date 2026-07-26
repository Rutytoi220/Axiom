import pytest
import sys
from axiom.tools.document_reader import ReadDocumentContentTool
from unittest.mock import MagicMock

@pytest.mark.asyncio
async def test_document_reader_pdf_fallback(tmp_path, monkeypatch):
    t = ReadDocumentContentTool(str(tmp_path))
    p = tmp_path / "test.pdf"
    p.touch()

    # Block both pdfplumber and PyPDF2
    monkeypatch.setitem(sys.modules, "pdfplumber", None)
    monkeypatch.setitem(sys.modules, "PyPDF2", None)

    res = await t.execute({'file_path': str(p)})
    assert not res.success  # zero selectable chars

    # Mock PyPDF2 but raise Exception
    mock_pypdf2 = MagicMock()
    mock_pypdf2.PdfReader.side_effect = Exception("pypdf2 fail")
    monkeypatch.setitem(sys.modules, "PyPDF2", mock_pypdf2)
    res = await t.execute({'file_path': str(p)})
    assert not res.success
    
    # Mock PyPDF2 returns empty text
    mock_reader = MagicMock()
    mock_page = MagicMock()
    mock_page.extract_text.return_value = ""
    mock_reader.pages = [mock_page]
    mock_pypdf2.PdfReader.side_effect = None
    mock_pypdf2.PdfReader.return_value = mock_reader
    res = await t.execute({'file_path': str(p)})
    assert not res.success

    # Mock pdfplumber exception
    mock_pdfplumber = MagicMock()
    mock_pdfplumber.open.side_effect = Exception("plumber fail")
    monkeypatch.setitem(sys.modules, "pdfplumber", mock_pdfplumber)
    res = await t.execute({'file_path': str(p)})
    assert not res.success

    # Mock pdfplumber with valid text (>= 15 chars)
    class MockPlumberPDF:
        class Page:
            def extract_text(self): return "this is a valid text with more than 15 chars"
        pages = [Page()]
        def __enter__(self): return self
        def __exit__(self, *args): pass
    mock_pdfplumber.open.side_effect = None
    mock_pdfplumber.open.return_value = MockPlumberPDF()
    res = await t.execute({'file_path': str(p)})
    assert res.success

@pytest.mark.asyncio
async def test_document_reader_max_size(tmp_path):
    t = ReadDocumentContentTool(str(tmp_path))
    p = tmp_path / "test.txt"
    p.write_text("x" * (t.MAX_CONTEXT_LENGTH + 10))
    res = await t.execute({'file_path': str(p)})
    assert res.success
    assert "TRUNCATED" in res.output['content']

@pytest.mark.asyncio
async def test_document_reader_missing_path():
    t = ReadDocumentContentTool(".")
    res = await t.execute({})
    assert not res.success
