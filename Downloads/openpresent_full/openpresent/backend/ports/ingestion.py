"""
Document Ingestion Port — Technical Blueprint Section 3.1.

Responsibility: turn an uploaded file into clean, structured text.
This is the untrusted-input security boundary (Blueprint Section 11 / ADR-009):
adapters must only ever return plain extracted text, never execute or
interpret content found inside the document.
"""

from typing import Protocol


class UnsupportedFileTypeError(Exception):
    pass


class CorruptFileError(Exception):
    pass


class IngestionPort(Protocol):
    """Any adapter implementing this port must satisfy the contract tests
    in tests/contract/test_ingestion_port.py."""

    def supported_extensions(self) -> list[str]:
        """e.g. ['.txt', '.md']"""
        ...

    def extract_text(self, file_bytes: bytes, filename: str) -> str:
        """
        Extract plain text from the given file bytes.

        Raises UnsupportedFileTypeError if filename's extension isn't
        supported by this adapter, CorruptFileError if the file can't
        be parsed.
        """
        ...
