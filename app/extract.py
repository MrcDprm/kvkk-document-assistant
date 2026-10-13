"""Turn an uploaded .txt, .pdf or .docx file into plain text.

Uploaded bytes are not trusted: the type is checked from the file content (not only the
extension), sizes are limited before anything is unpacked, and every failure becomes an
ExtractError with a short code that the UI turns into a message in the user's language.
"""

import io
import re
import unicodedata
import zipfile

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAX_PDF_PAGES = 300
# A .docx is a zip file. Limits on the unpacked size stop "zip bombs"
# (a few KB that expand to gigabytes in memory).
MAX_DOCX_UNCOMPRESSED_BYTES = 50 * 1024 * 1024
MAX_DOCX_ENTRIES = 1000


class ExtractError(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def normalize_text(text: str, max_chars: int) -> str:
    """Clean text from any source (upload or paste) and enforce the length limit."""
    # PDFs often store "ş" as "s" + combining cedilla; NFC joins them so the recognizers see "ş".
    text = unicodedata.normalize("NFC", text)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\x00", "")
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not text:
        raise ExtractError("no_text")
    if len(text) > max_chars:
        raise ExtractError("text_too_long")
    return text


def _kind_from_content(data: bytes) -> str:
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"PK\x03\x04"):
        return "docx"
    return "txt"


def _txt(data: bytes) -> str:
    if b"\x00" in data[:4096]:
        raise ExtractError("unsupported_type")  # binary file renamed to .txt
    for encoding in ("utf-8-sig", "cp1254"):  # cp1254: Turkish Windows (older Notepad files)
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise ExtractError("corrupt")


def _pdf(data: bytes) -> str:
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            # Some PDFs are "encrypted" with an empty password only to block editing.
            try:
                if not reader.decrypt(""):
                    raise ExtractError("encrypted")
            except (NotImplementedError, PdfReadError):
                raise ExtractError("encrypted")
        if len(reader.pages) > MAX_PDF_PAGES:
            raise ExtractError("too_many_pages")
        return "\n\n".join(page.extract_text() or "" for page in reader.pages)
    except ExtractError:
        raise
    except Exception:
        # pypdf raises many different exceptions for broken files.
        raise ExtractError("corrupt")


def _docx(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
            if len(entries) > MAX_DOCX_ENTRIES:
                raise ExtractError("corrupt")
            if sum(e.file_size for e in entries) > MAX_DOCX_UNCOMPRESSED_BYTES:
                raise ExtractError("too_large")
            if "word/document.xml" not in archive.namelist():
                raise ExtractError("unsupported_type")  # some other zip file
        document = Document(io.BytesIO(data))
    except ExtractError:
        raise
    except Exception:
        raise ExtractError("corrupt")

    # Walk the body in order so tables stay where they are in the document.
    blocks: list[str] = []
    for child in document.element.body.iterchildren():
        tag = child.tag.rsplit("}", 1)[-1]
        if tag == "p":
            blocks.append(Paragraph(child, document).text)
        elif tag == "tbl":
            for row in Table(child, document).rows:
                blocks.append(" | ".join(cell.text.strip() for cell in row.cells))
    return "\n".join(blocks)


_EXTRACTORS = {"txt": _txt, "pdf": _pdf, "docx": _docx}


def extract_text(filename: str, data: bytes, max_bytes: int, max_chars: int) -> str:
    if len(data) > max_bytes:
        raise ExtractError("too_large")
    extension = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if extension not in _EXTRACTORS:
        raise ExtractError("unsupported_type")
    # The extension and the content must agree: a PDF renamed to .txt is rejected.
    if _kind_from_content(data) != extension:
        raise ExtractError("unsupported_type")
    return normalize_text(_EXTRACTORS[extension](data), max_chars)
