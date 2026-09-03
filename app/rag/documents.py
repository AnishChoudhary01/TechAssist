"""Load supported technical-document formats into text-bearing pages."""

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from pypdf import PdfReader


class UnsupportedDocumentError(ValueError):
    """Raised when an uploaded file type is not supported."""


@dataclass(frozen=True, slots=True)
class DocumentPage:
    content: str
    source: str
    page: int | None = None


class DocumentLoader:
    """Loads plain text, Markdown, and PDF technical documentation."""

    supported_extensions = {".txt", ".md", ".pdf"}

    def load_bytes(self, filename: str, content: bytes) -> list[DocumentPage]:
        """Read uploaded document bytes into one or more text pages."""
        source = Path(filename).name
        suffix = Path(source).suffix.lower()
        if suffix not in self.supported_extensions:
            raise UnsupportedDocumentError("Supported file types are .txt, .md, and .pdf.")

        if suffix == ".pdf":
            reader = PdfReader(BytesIO(content))
            pages: list[DocumentPage] = []
            for index, page in enumerate(reader.pages):
                text = page.extract_text() or ""
                if text.strip():
                    pages.append(DocumentPage(content=text, source=source, page=index + 1))
            return pages

        text = content.decode("utf-8", errors="replace").strip()
        return [DocumentPage(content=text, source=source)] if text else []

    def load_directory(self, directory: str) -> list[DocumentPage]:
        """Load all supported documents under a configured local directory."""
        root = Path(directory)
        if not root.exists():
            return []

        pages: list[DocumentPage] = []
        for path in root.rglob("*"):
            if path.is_file() and path.suffix.lower() in self.supported_extensions:
                pages.extend(self.load_bytes(path.name, path.read_bytes()))
        return pages
