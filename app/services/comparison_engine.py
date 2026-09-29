from __future__ import annotations

from app.models.schemas import ComparisonRow, OnboardingPlan, Requirement
from app.services.source_index import SourceIndex


def compare(
    plan: OnboardingPlan,
    requirements: list[Requirement],
    source_index: SourceIndex | None = None,
) -> list[ComparisonRow]:
    expected = {r.requirement_id: r for r in requirements}
    generated = set()
    source_by_requirement: dict[str, list] = {}

    for module in plan.modules:
        for rid in module.requirement_ids:
            generated.add(rid)
            source_by_requirement.setdefault(rid, []).extend(module.required_sources)
    for task in plan.tasks:
        for rid in task.requirement_ids:
            generated.add(rid)
            source_by_requirement.setdefault(rid, []).append(task.source)
    for quiz in plan.quiz:
        generated.add(quiz.requirement_id)
        source_by_requirement.setdefault(quiz.requirement_id, []).append(quiz.source)

    rows = []
    for rid, requirement in expected.items():
        present = rid in generated
        refs = source_by_requirement.get(rid, [])
        source_valid = any(
            ref.document_id == requirement.source.document_id
            and ref.document_version == requirement.source.document_version
            and str(ref.section_id) == str(requirement.source.section_id)
            and (source_index is None or not source_index.validate_ref(ref))
            for ref in refs
        )
        rows.append(
            ComparisonRow(
                requirement_id=rid,
                role=requirement.role,
                python_expected=requirement.mandatory,
                genai_present=present,
                match=(not requirement.mandatory or present),
                source_valid=source_valid,
                validation_status=("Match" if present and source_valid else "Review" if present else "Missing"),
            )
        )
    return rows
