"""PDF extraction and chunking helpers for the eComBot knowledge base."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from ..config.settings import PDF_DIR

MAX_CHUNK_CHARS = 900
CHUNK_OVERLAP_CHARS = 150


def _clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _is_heading(line: str) -> bool:
    stripped = line.strip()
    if not stripped or len(stripped) > 90:
        return False
    if stripped.endswith("?"):
        return True
    if stripped.isupper():
        return True
    if not re.match(r"^([0-9]+[.)]\s+)?[A-Za-z0-9][A-Za-z0-9 &/-]+$", stripped):
        return False

    words = stripped.split()
    if len(words) > 6:
        return False
    lowercase_words = {
        word
        for word in words
        if word.isalpha() and word[0].islower() and word.lower() not in {"and", "or", "for"}
    }
    return not lowercase_words


def _document_title(pdf_path: Path, pages: list[str]) -> str:
    for page_text in pages:
        for line in page_text.splitlines():
            stripped = line.strip()
            if stripped:
                return stripped[:120]
    return pdf_path.stem.replace("-", " ").title()


def _split_sections(page_text: str) -> list[tuple[str, str]]:
    """Return ``(section, text)`` pairs while preserving heading context."""
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    if not lines:
        return []

    sections: list[tuple[str, list[str]]] = []
    current_section = "General"
    current_lines: list[str] = []

    for line in lines:
        if _is_heading(line):
            if current_lines:
                sections.append((current_section, current_lines))
                current_lines = []
            current_section = line
            current_lines.append(line)
        else:
            current_lines.append(line)

    if current_lines:
        sections.append((current_section, current_lines))

    return [(section, "\n".join(section_lines).strip()) for section, section_lines in sections]


def _chunk_text(text: str, max_chars: int = MAX_CHUNK_CHARS) -> list[str]:
    """Split text into readable chunks with overlap between long chunks."""
    paragraphs = [paragraph.strip() for paragraph in re.split(r"\n\s*\n", text) if paragraph.strip()]
    if not paragraphs:
        return []

    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        if len(paragraph) > max_chars:
            if current:
                chunks.append(current.strip())
                current = ""
            start = 0
            while start < len(paragraph):
                end = min(start + max_chars, len(paragraph))
                chunks.append(paragraph[start:end].strip())
                if end == len(paragraph):
                    break
                start = max(0, end - CHUNK_OVERLAP_CHARS)
            continue

        candidate = f"{current}\n\n{paragraph}".strip() if current else paragraph
        if len(candidate) <= max_chars:
            current = candidate
            continue

        chunks.append(current.strip())
        overlap = current[-CHUNK_OVERLAP_CHARS:].strip()
        current = f"{overlap}\n\n{paragraph}".strip() if overlap else paragraph

    if current:
        chunks.append(current.strip())

    return chunks


def load_pdf_chunks(pdf_dir: Path = PDF_DIR) -> list[dict[str, Any]]:
    """Read PDF files and return chunks with traceable source metadata."""
    if not pdf_dir.exists():
        return []

    chunks: list[dict[str, Any]] = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        reader = PdfReader(str(pdf_path))
        page_texts = [_clean_text(page.extract_text() or "") for page in reader.pages]
        title = _document_title(pdf_path, page_texts)

        for page_number, page_text in enumerate(page_texts, start=1):
            if not page_text:
                continue

            for section, section_text in _split_sections(page_text):
                for chunk_index, chunk_text in enumerate(_chunk_text(section_text), start=1):
                    if section == "General" and len(chunk_text) < 80:
                        continue
                    chunks.append(
                        {
                            "id": (
                                f"pdf:{pdf_path.stem}:"
                                f"p{page_number}:s{len(chunks) + 1}:c{chunk_index}"
                            ),
                            "text": chunk_text,
                            "metadata": {
                                "source": pdf_path.name,
                                "source_file": pdf_path.name,
                                "document_title": title,
                                "section": section,
                                "page": page_number,
                                "doc_type": "pdf",
                                "kind": "pdf_knowledge",
                                "title": section,
                            },
                        }
                    )

    return chunks
