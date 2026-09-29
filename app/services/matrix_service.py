from __future__ import annotations

from typing import Any

from app.models.schemas import Requirement, SourceRef
from app.services.ground_truth import requirements_for_role
from app.services.requirement_engine import build_matrix as build_source_matrix


def _source_location(chunks: list[dict[str, Any]], document_id: str, section_id: str, version: str) -> str:
    matches = [
        c for c in chunks
        if c.get("document_id") == document_id
        and str(c.get("section_id")) == str(section_id)
        and str(c.get("version")) == str(version)
    ]
    if matches:
        return str(matches[0].get("location") or f"section:{section_id}")
    return f"section:{section_id}"


def _to_requirement(row, chunks: list[dict[str, Any]]) -> Requirement:
    versions = [
        str(c.get("version"))
        for c in chunks
        if c.get("document_id") == row.source_document_id
        and str(c.get("section_id")) == str(row.source_section_id)
    ]
    version = versions[0] if versions else "unknown"
    text = f"{row.policy_requirement}. {row.process_requirement}."
    return Requirement(
        requirement_id=row.requirement_id,
        role=row.role,
        title=row.policy_requirement or row.process_requirement,
        category="process" if row.process_requirement else "policy",
        mandatory=row.mandatory,
        priority=row.priority,
        source=SourceRef(
            document_id=row.source_document_id,
            document_version=version,
            section_id=str(row.source_section_id),
            location=_source_location(chunks, row.source_document_id, row.source_section_id, version),
        ),
        requirement_text=text,
        assessment_topic=row.competency,
        department=row.department,
        policy_requirement=row.policy_requirement,
        process_requirement=row.process_requirement,
        competency=row.competency,
        assessment_required=row.assessment_required,
        due_stage=row.due_stage,
        origin="ground_truth",
    )


def build_role_matrix(role: str, chunks: list[dict[str, Any]]) -> tuple[list[Requirement], str]:
    """Use the supplied independent matrix when available; otherwise derive candidates from sources."""
    rows = requirements_for_role(role)
    if rows:
        return [_to_requirement(row, chunks) for row in rows], "ground_truth"
    return build_source_matrix(chunks, role), "source_extracted"
