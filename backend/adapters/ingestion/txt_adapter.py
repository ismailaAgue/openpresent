from backend.ports.ingestion import IngestionPort, UnsupportedFileTypeError, CorruptFileError


class TxtIngestionAdapter(IngestionPort):
    """Handles .txt and .md — plain text passthrough, per Blueprint 3.1."""

    def supported_extensions(self) -> list[str]:
        return [".txt", ".md"]

    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        ext = _ext(filename)
        if ext not in self.supported_extensions():
            raise UnsupportedFileTypeError(f"{ext} not supported by TxtIngestionAdapter")
        try:
            return file_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            raise CorruptFileError(f"Could not decode {filename} as UTF-8 text") from e


def _ext(filename: str) -> str:
    idx = filename.rfind(".")
    return filename[idx:].lower() if idx != -1 else ""
