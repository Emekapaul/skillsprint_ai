from __future__ import annotations

import re

from app.models.schemas import Requirement, SourceRef

MANDATORY = re.compile(r"\b(must|required|required to|mandatory|shall|needs to)\b", re.I)
OPTIONAL = re.compile(r"\b(should|recommended|optional|may|can)\b", re.I)
NORMATIVE = re.compile(
    r"\b(must|required|required to|mandatory|shall|needs to|should|recommended|optional|may|can)\b",
    re.I,
)
METADATA = re.compile(
    r"^\s*(document\s*(id|type|title)|version|effective\s*date|expiry\s*date|status|owner|approved\s*by|review\s*date)\s*[:\-]",
    re.I,
)
HEADING = re.compile(
    r"^\s*(\d+(\.\d+)*[\.)]?\s+.+|(section|chapter|appendix)\s+\w+.*)$",
    re.I,
)
DATASET_CONTEXT = re.compile(
    r"\b(competition\s+dataset|training\s+and\s+validation\s+demonstrations|authoritative\s+company\s+content|fictional\s+document)\b",
    re.I,
)
GENERIC_CONTROL = re.compile(
    r"^(the\s+)?responsible\s+owner\s+must\s+maintain\s+the\s+associated\s+record\s+where\s+applicable\s+and\s+escalate\s+exceptions\s+through\s+the\s+documented\s+escalation\s+process\.?$",
    re.I,
)


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").split()).strip()


def is_metadata(text: str) -> bool:
    return bool(METADATA.search(text))


def is_heading(text: str) -> bool:
    return bool(HEADING.match(text))


def split_normative_clauses(text: str) -> list[str]:
    text = normalize_text(text)
    if not text:
        return []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    clauses: list[str] = []
    for sentence in sentences:
        sentence = normalize_text(sentence)
        if not sentence or DATASET_CONTEXT.search(sentence):
            continue
        if GENERIC_CONTROL.match(sentence):
            continue
        if NORMATIVE.search(sentence):
            clauses.append(sentence)
            continue
        if re.search(r"\b(only\s+the\s+latest|only\s+authorized|is\s+authoritative|are\s+authoritative)\b", sentence, re.I):
            clauses.append(sentence)
    return clauses


def infer_mandatory(text: str) -> bool:
    if re.search(r"\bonly\s+the\s+latest\b.*?\bauthoritative\b", text, re.I):
        return True
    matches = list(re.finditer(r"\b(must|required|required to|mandatory|shall|needs to|should|recommended|optional|may|can)\b", text, re.I))
    if not matches:
        return False
    return matches[0].group(1).lower() in {"must", "required", "required to", "mandatory", "shall", "needs to"}


def infer_category(text: str) -> str:
    lower = text.lower()
    if re.search(r"\b(procedure|process|sop|workflow|escalate|escalation)\b", lower):
        return "process"
    if re.search(r"\b(competency|competence|skill|knowledge)\b", lower):
        return "competency"
    if re.search(r"\b(assessment|quiz|test|demonstrate|demonstration)\b", lower):
        return "assessment"
    if re.search(r"\b(task|complete|perform)\b", lower):
        return "task"
    return "policy"


def infer_priority(text: str, mandatory: bool) -> str:
    if mandatory:
        return "High"
    if re.search(r"\b(recommended|important|best practice|should)\b", text, re.I):
        return "Medium"
    return "Low"


def infer_title(text: str, heading: str | None = None) -> str:
    heading = normalize_text(heading)
    if heading:
        return heading
    text = normalize_text(text)
    return text if len(text) <= 80 else text[:77].rstrip() + "..."


def build_requirement(
    clause: str,
    role: str,
    document_id: str,
    version: str,
    section_id: str,
    location: str,
    idx: int,
    heading: str | None = None,
) -> Requirement | None:
    clause = normalize_text(clause)
    if len(clause) < 20:
        return None
    mandatory = infer_mandatory(clause)
    return Requirement(
        requirement_id=f"REQ-{idx:04d}",
        role=role,
        title=infer_title(clause, heading),
        category=infer_category(clause),
        mandatory=mandatory,
        priority=infer_priority(clause, mandatory),
        source=SourceRef(
            document_id=document_id,
            document_version=version,
            section_id=str(section_id),
            location=location,
        ),
        requirement_text=clause,
        origin="source_extracted",
    )


def applicability_text_for_chunk(chunk: dict) -> str:
    heading = normalize_text(chunk.get("heading") or "")
    text = normalize_text(chunk.get("text") or "")
    if heading and text and heading != text:
        return f"{heading} {text}"
    return text or heading


def build_matrix(chunks: list[dict], role: str) -> list[Requirement]:
    """Extract source-backed candidate requirements for roles without an external matrix."""
    requirements: list[Requirement] = []
    counter = 1
    seen: set[tuple[str, str, str]] = set()

    for chunk in chunks:
        text = normalize_text(chunk.get("text", ""))
        if len(text) < 20 or is_metadata(text) or is_heading(text):
            continue

        clauses = split_normative_clauses(text)
        for clause in clauses:
            key = (
                str(chunk.get("document_id", "")),
                str(chunk.get("section_id", "")),
                clause.casefold(),
            )
            if key in seen:
                continue
            seen.add(key)
            requirement = build_requirement(
                clause=clause,
                role=role,
                document_id=str(chunk.get("document_id", "")),
                version=str(chunk.get("version", "1.0")),
                section_id=str(chunk.get("section_id", "")),
                location=str(chunk.get("location", "unknown")),
                idx=counter,
                heading=chunk.get("heading"),
            )
            if requirement is not None:
                requirements.append(requirement)
                counter += 1

    return requirements
