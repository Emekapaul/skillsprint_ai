from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

from docx import Document
from pypdf import PdfReader

from app.security.prompt_guard import sanitize_source


SUPPORTED_EXTENSIONS = {".pdf", ".docx"}

SECTION_RE = re.compile(r"^\s*(\d+(?:\.\d+)*)[.)]?\s+(.+?)\s*$")
METADATA_PATTERNS = {
    "document_id": re.compile(r"\bDocument ID\s*:\s*([A-Za-z]+-\d+)\b", re.I),
    "document_type": re.compile(r"\bDocument Type\s*:\s*([^|\n]+)", re.I),
    "version": re.compile(r"\bVersion\s*:\s*([^|\n]+)", re.I),
    "effective_date": re.compile(r"\bEffective Date\s*:\s*([^|\n]+)", re.I),
    "status": re.compile(r"\bStatus\s*:\s*([^|\n]+)", re.I),
    "owner": re.compile(r"\bOwner\s*:\s*([^|\n]+)", re.I),
}


def calculate_file_hash(path: str) -> str:
    sha256 = hashlib.sha256()
    with open(path, "rb") as file:
        while True:
            block = file.read(1024 * 1024)
            if not block:
                break
            sha256.update(block)
    return sha256.hexdigest()


def make_chunk_id(document_id: str, version: str, index: int, text: str) -> str:
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    safe_version = re.sub(r"[^A-Za-z0-9]+", "-", version).strip("-") or "1-0"
    return f"{document_id}-V{safe_version}-CH-{index:03d}-{digest}"


def parse_section_heading(text: str) -> tuple[str | None, str | None]:
    first_line = (text or "").strip().splitlines()[0].strip() if text else ""
    if not first_line or len(first_line) > 180:
        return None, None
    match = SECTION_RE.match(first_line)
    if match:
        return match.group(1), match.group(2).strip()
    if first_line.lower() == "document control":
        return "Document Control", first_line
    return None, None


def detect_heading(text: str) -> str | None:
    _, heading = parse_section_heading(text)
    if heading:
        return heading
    first_line = (text or "").strip().splitlines()[0].strip() if text else ""
    if not first_line or len(first_line) > 120:
        return None
    if first_line.isupper() or first_line.endswith(":"):
        return first_line
    return None


def split_text(text: str, max_characters: int = 1800) -> list[str]:
    paragraphs = [
        paragraph.strip()
        for paragraph in re.split(r"\n\s*\n", text or "")
        if paragraph.strip()
    ]

    chunks: list[str] = []
    current = ""
    for paragraph in paragraphs:
        if not current:
            current = paragraph
            continue
        candidate = f"{current}\n\n{paragraph}"
        if len(candidate) <= max_characters:
            current = candidate
        else:
            chunks.append(current)
            current = paragraph
    if current:
        chunks.append(current)

    final_chunks: list[str] = []
    for chunk in chunks:
        if len(chunk) <= max_characters:
            final_chunks.append(chunk)
        else:
            for start in range(0, len(chunk), max_characters):
                final_chunks.append(chunk[start : start + max_characters])
    return final_chunks


def _split_pdf_page(page_text: str, page_number: int) -> list[dict[str, Any]]:
    lines = [line.strip() for line in (page_text or "").splitlines() if line.strip()]
    if not lines:
        return []

    parts: list[dict[str, Any]] = []
    current_section: str | None = None
    current_heading: str | None = None
    current_lines: list[str] = []

    def flush() -> None:
        if not current_lines:
            return
        parts.append(
            {
                "location": f"page:{page_number}",
                "page": page_number,
                "section": current_section,
                "heading": current_heading,
                "text": "\n".join(current_lines),
            }
        )

    for line in lines:
        section_id, heading = parse_section_heading(line)
        if section_id:
            flush()
            current_lines.clear()
            current_section = section_id
            current_heading = heading
            continue
        current_lines.append(line)

    flush()

    if not any(p.get("section") for p in parts):
        for part in parts:
            part["section"] = f"page:{page_number}"
    return parts


def extract_pdf(path: str) -> list[dict[str, Any]]:
    reader = PdfReader(path)
    output: list[dict[str, Any]] = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        output.extend(_split_pdf_page(text, page_number))
    return output


def extract_docx(path: str) -> list[dict[str, Any]]:
    document = Document(path)
    output: list[dict[str, Any]] = []
    current_section: str | None = None
    current_heading: str | None = None

    for paragraph_number, paragraph in enumerate(document.paragraphs, start=1):
        text = paragraph.text.strip()
        if not text:
            continue
        style_name = paragraph.style.name if paragraph.style else ""
        is_heading = style_name.lower().startswith("heading")
        section_id, numbered_heading = parse_section_heading(text)
        if is_heading:
            current_section = section_id or f"heading:{paragraph_number}"
            current_heading = numbered_heading or text
        output.append(
            {
                "location": f"paragraph:{paragraph_number}",
                "page": None,
                "section": current_section,
                "heading": current_heading,
                "style": style_name,
                "text": text,
            }
        )

    for table_number, table in enumerate(document.tables, start=1):
        for row_number, row in enumerate(table.rows, start=1):
            cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
            if not cells:
                continue
            output.append(
                {
                    "location": f"table:{table_number}:row:{row_number}",
                    "page": None,
                    "section": current_section,
                    "heading": current_heading,
                    "style": "Table",
                    "text": " | ".join(cells),
                }
            )

    return output


def extract_metadata(parts: list[dict[str, Any]], file_stem: str) -> dict[str, Any]:
    text = "\n".join(str(part.get("text", "")) for part in parts[:12])
    metadata: dict[str, Any] = {"title": file_stem}
    for key, pattern in METADATA_PATTERNS.items():
        match = pattern.search(text)
        if match:
            metadata[key] = match.group(1).strip()
    return metadata


def build_chunks(parts: list[dict], document_id: str, version: str) -> list[dict]:
    chunks = []
    chunk_index = 1
    for part in parts:
        text = part["text"]
        for piece in split_text(text):
            _, injection_flags = sanitize_source(piece)
            section_id = part.get("section") or f"chunk:{chunk_index:03d}"
            heading = part.get("heading") or detect_heading(piece)
            chunks.append(
                {
                    "document_id": document_id,
                    "chunk_id": make_chunk_id(document_id, version, chunk_index, piece),
                    "version": version,
                    "section_id": str(section_id),
                    "heading": heading,
                    "location": part["location"],
                    "page": part.get("page"),
                    "text": piece,
                    "prompt_injection_flags": injection_flags,
                }
            )
            chunk_index += 1
    return chunks


def process_document(path: str, document_id: str, version: str | None = None) -> dict:
    file_path = Path(path)
    if not file_path.exists():
        raise ValueError(f"Document does not exist: {path}")
    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise ValueError("Only PDF and DOCX are supported.")
    if file_path.stat().st_size == 0:
        raise ValueError("The uploaded document is empty.")

    parts = extract_pdf(path) if extension == ".pdf" else extract_docx(path)
    if not parts:
        raise ValueError("No readable text was found in the document.")

    metadata = extract_metadata(parts, file_path.stem)
    detected_version = str(metadata.get("version") or version or "1.0").strip()
    effective_version = str(version or detected_version).strip()
    effective_document_id = str(metadata.get("document_id") or document_id).upper()
    chunks = build_chunks(parts, effective_document_id, effective_version)

    return {
        "document_id": effective_document_id,
        "title": file_path.stem,
        "filename": file_path.name,
        "file_type": extension,
        "file_hash": calculate_file_hash(path),
        "version": effective_version,
        "detected_version": detected_version,
        "effective_date": metadata.get("effective_date"),
        "document_type": metadata.get("document_type"),
        "owner": metadata.get("owner"),
        "status": str(metadata.get("status") or "active").strip().lower(),
        "page_count": len({part["page"] for part in parts if part.get("page") is not None}),
        "source_parts": len(parts),
        "chunks": chunks,
    }
