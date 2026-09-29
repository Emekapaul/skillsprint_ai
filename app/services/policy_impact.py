from __future__ import annotations

import re
from typing import Any

from app.services.ground_truth import load_ground_truth


def _version_key(version: str) -> tuple:
    parts = []
    for token in re.split(r"[.\-_]", str(version)):
        parts.append(int(token) if token.isdigit() else token.lower())
    return tuple(parts)


def _section_text(document: dict[str, Any]) -> dict[str, str]:
    sections: dict[str, list[str]] = {}
    for chunk in document.get("chunks", []):
        sections.setdefault(str(chunk.get("section_id", "")), []).append(str(chunk.get("text", "")))
    return {section: " ".join(values).strip() for section, values in sections.items()}


def impact_analysis(old_docs: list[dict], new_doc: dict) -> dict:
    same_id = [d for d in old_docs if d.get("document_id") == new_doc.get("document_id")]
    previous = [d for d in same_id if d.get("version") != new_doc.get("version")]
    previous = sorted(previous, key=lambda d: _version_key(d.get("version", "0")))
    old = previous[-1] if previous else None

    if not old:
        return {
            "change_type": "new_document",
            "previous_version": None,
            "new_version": new_doc.get("version"),
            "changed_sections": [],
            "affected_requirement_ids": [],
            "recommendation": "Review new source before generation",
        }

    old_sections = _section_text(old)
    new_sections = _section_text(new_doc)
    changed_sections = sorted(
        section for section in set(old_sections) | set(new_sections)
        if old_sections.get(section, "") != new_sections.get(section, "")
    )

    affected = []
    try:
        for requirement in load_ground_truth():
            if (
                requirement.source_document_id == new_doc.get("document_id")
                and str(requirement.source_section_id) in changed_sections
            ):
                affected.append(requirement.requirement_id)
    except FileNotFoundError:
        pass

    return {
        "change_type": "updated" if changed_sections else "unchanged",
        "previous_version": old.get("version"),
        "new_version": new_doc.get("version"),
        "changed_sections": changed_sections,
        "affected_requirement_ids": affected,
        "recommendation": "Selective regeneration required" if affected else ("Review changed source" if changed_sections else "No regeneration required"),
    }
