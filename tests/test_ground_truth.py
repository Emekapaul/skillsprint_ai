from app.services.ground_truth import load_ground_truth, requirements_for_role
from app.services.matrix_service import build_role_matrix
from app.services.document_processor import process_document


def test_ground_truth_has_expected_shape():
    rows = load_ground_truth()
    assert len(rows) == 160
    assert len({r.role for r in rows}) == 10
    assert sum(r.mandatory for r in rows) == 120


def test_role_matrix_uses_independent_ground_truth_when_available():
    doc = process_document(
        "nexasphere_company_pack/documents/SUP-001_Customer_Support_SOP.docx",
        "SUP-001",
        None,
    )
    matrix, origin = build_role_matrix("Customer Support Executive", doc["chunks"])
    assert origin == "ground_truth"
    assert len(matrix) == 16
    assert sum(r.mandatory for r in matrix) == 12
    assert matrix[0].requirement_id == "R001"
