from pathlib import Path

from app.services.document_processor import process_document


def test_sample_pdf():
    pdf = next(Path("data/sample_documents").glob("*.pdf"))
    result = process_document(str(pdf), "TEST-DOC", "1.0")
    assert result["chunks"]
    assert all("document_id" in c and "chunk_id" in c for c in result["chunks"])


def test_docx_preserves_numbered_sections_and_detects_version():
    result = process_document(
        "nexasphere_company_pack/documents/SUP-001_Customer_Support_SOP.docx",
        "SUP-001",
        None,
    )
    assert result["version"] == "2.1"
    section_ids = {chunk["section_id"] for chunk in result["chunks"]}
    assert "1" in section_ids
    assert "5" in section_ids
    assert "Document Control" in section_ids
