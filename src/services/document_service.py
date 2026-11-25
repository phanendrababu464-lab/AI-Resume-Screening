"""Validate uploaded document structure and bound expanded DOCX size."""

import io
from zipfile import ZipFile, BadZipFile


def check_document(stream: io.BytesIO) -> None:
    prefix = stream.read(8)
    stream.seek(0)
    if stream.name.lower().endswith(".pdf"):
        if not prefix.startswith(b"%PDF-"):
            raise ValueError("Invalid PDF signature.")
        return
    if not prefix.startswith(b"PK"):
        raise ValueError("Invalid DOCX signature.")
    try:
        with ZipFile(stream) as archive:
            entries = archive.infolist()
            if len(entries) > 1000 or sum(item.file_size for item in entries) > 30 * 1024 * 1024:
                raise ValueError("DOCX expanded size exceeds the limit.")
            if "word/document.xml" not in archive.namelist():
                raise ValueError("Invalid DOCX document.")
    except BadZipFile as exc:
        raise ValueError("Invalid DOCX archive.") from exc
    finally:
        stream.seek(0)


def read_job_text(stream: io.BytesIO) -> str:
    from src.parser import extract_text

    check_document(stream)
    return extract_text(stream, stream.name)
