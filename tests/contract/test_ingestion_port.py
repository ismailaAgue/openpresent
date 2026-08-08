import pytest
from backend.adapters.ingestion.txt_adapter import TxtIngestionAdapter
from backend.adapters.ingestion.pdf_adapter import PdfIngestionAdapter
from backend.ports.ingestion import UnsupportedFileTypeError, CorruptFileError

ADAPTERS = [TxtIngestionAdapter(), PdfIngestionAdapter()]


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_rejects_unsupported_extension(adapter):
    with pytest.raises(UnsupportedFileTypeError):
        adapter.extract_text(b"data", "file.xyz_not_real")


def test_txt_adapter_extracts_plain_text():
    adapter = TxtIngestionAdapter()
    text = adapter.extract_text("Hello world".encode("utf-8"), "essay.txt")
    assert text == "Hello world"


def test_txt_adapter_rejects_bad_encoding():
    adapter = TxtIngestionAdapter()
    with pytest.raises(CorruptFileError):
        adapter.extract_text(b"\xff\xfe\x00\x81", "essay.txt")
