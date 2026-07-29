import io
from backend.ports.ingestion import IngestionPort, UnsupportedFileTypeError, CorruptFileError


class PdfIngestionAdapter(IngestionPort):
    """Extracts text from PDF files using pypdf."""

    def supported_extensions(self) -> list[str]:
        return [".pdf"]

    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        if not filename.lower().endswith(".pdf"):
            raise UnsupportedFileTypeError(f"{filename} not supported by PdfIngestionAdapter")
        try:
            from pypdf import PdfReader
        except ImportError as e:
            raise RuntimeError(
                "pypdf is required for PDF ingestion. Install with: "
                "pip install pypdf --break-system-packages"
            ) from e

        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            pages_text = [page.extract_text() or "" for page in reader.pages]
            text = "\n\n".join(pages_text).strip()
        except Exception as e:
            raise CorruptFileError(f"Could not parse {filename} as PDF: {e}") from e

        if not text:
            raise CorruptFileError(
                f"{filename} produced no extractable text (likely a scanned/image PDF)"
            )
        return text
