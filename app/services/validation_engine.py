from __future__ import annotations

import re
from collections import Counter, defaultdict
from typing import Any

from app.models.schemas import (
    OnboardingPlan,
    Requirement,
    ValidationFinding,
    ValidationResult,
)
from app.services.source_index import SourceIndex


def _as_source_index(valid_documents: Any, source_index: SourceIndex | None) -> SourceIndex:
    if source_index is not None:
        return source_index
    if isinstance(valid_documents, dict):
        documents = [
            {"document_id": document_id, "version": version, "status": "active", "chunks": []}
            for document_id, version in valid_documents.items()
        ]
    else:
        documents = list(valid_documents or [])
    return SourceIndex(documents)


def _all_requirement_ids(plan: OnboardingPlan) -> list[str]:
    return [
        *[rid for module in plan.modules for rid in module.requirement_ids],
        *[rid for task in plan.tasks for rid in task.requirement_ids],
        *[quiz.requirement_id for quiz in plan.quiz],
    ]


def _matching_source(requirement: Requirement, source) -> bool:
    return (
        source.document_id == requirement.source.document_id
        and source.document_version == requirement.source.document_version
        and str(source.section_id) == str(requirement.source.section_id)
    )


def _source_refs_for_requirement(plan: OnboardingPlan, requirement_id: str) -> list:
    refs = []
    for module in plan.modules:
        if requirement_id in module.requirement_ids:
            refs.extend(module.required_sources)
    for task in plan.tasks:
        if requirement_id in task.requirement_ids:
            refs.append(task.source)
    for quiz in plan.quiz:
        if quiz.requirement_id == requirement_id:
            refs.append(quiz.source)
    return refs


def _find_module(plan: OnboardingPlan, requirement_id: str):
    for module in plan.modules:
        if requirement_id in module.requirement_ids:
            return module
    return None


def _find_task(plan: OnboardingPlan, requirement_id: str):
    for task in plan.tasks:
        if requirement_id in task.requirement_ids:
            return task
    return None


def _find_quiz(plan: OnboardingPlan, requirement_id: str):
    return next((q for q in plan.quiz if q.requirement_id == requirement_id), None)


def validate_plan(
    plan: OnboardingPlan,
    requirements: list[Requirement],
    valid_documents: Any,
    source_index: SourceIndex | None = None,
) -> ValidationResult:
    req_by_id = {r.requirement_id: r for r in requirements}
    mandatory = {r.requirement_id for r in requirements if r.mandatory}
    covered = set(_all_requirement_ids(plan))
    findings: list[ValidationFinding] = []

    source_index = _as_source_index(valid_documents, source_index)
    invalid_source_ids: set[str] = set()
    outdated_source_ids: set[str] = set()
    prompt_injection_source_ids: set[str] = set()

    # Validate every source reference, not just sources attached to modules.
    all_sources = []
    for module in plan.modules:
        all_sources.extend(module.required_sources)
    all_sources.extend(task.source for task in plan.tasks)
    all_sources.extend(quiz.source for quiz in plan.quiz)

    for source in all_sources:
        for code, message in source_index.validate_ref(source):
            severity = "error"
            if code == "OUTDATED_SOURCE_VERSION":
                outdated_source_ids.add(source.document_id)
            else:
                invalid_source_ids.add(source.document_id)
            findings.append(ValidationFinding(code=code, severity=severity, message=message))
        if source_index.ref_is_prompt_injected(source):
            prompt_injection_source_ids.add(source.document_id)
            findings.append(
                ValidationFinding(
                    code="PROMPT_INJECTION_SOURCE",
                    severity="error",
                    message=f"Generated content cites source material flagged for prompt injection: {source.document_id} / {source.section_id}.",
                )
            )

    unknown = covered - set(req_by_id)
    missing = mandatory - covered
    module_counts = Counter(rid for module in plan.modules for rid in module.requirement_ids)
    task_counts = Counter(rid for task in plan.tasks for rid in task.requirement_ids)
    quiz_counts = Counter(quiz.requirement_id for quiz in plan.quiz)
    duplicates = {
        rid
        for counts in (module_counts, task_counts, quiz_counts)
        for rid, count in counts.items()
        if count > 1 and rid in req_by_id
    }

    for rid in sorted(missing):
        findings.append(
            ValidationFinding(
                code="REQUIREMENT_MISSING",
                severity="error",
                message=f"Mandatory requirement {rid} is not covered.",
                requirement_id=rid,
            )
        )
    for rid in sorted(unknown):
        findings.append(
            ValidationFinding(
                code="UNSUPPORTED_REQUIREMENT",
                severity="error",
                message=f"Generated requirement {rid} is not in the ground-truth matrix.",
                requirement_id=rid,
            )
        )
    for rid in sorted(duplicates):
        findings.append(
            ValidationFinding(
                code="DUPLICATE_COVERAGE",
                severity="warning",
                message=f"Requirement {rid} is referenced multiple times across generated content.",
                requirement_id=rid,
            )
        )

    assessment_missing: set[str] = set()
    due_stage_mismatch: set[str] = set()
    contradiction_ids: set[str] = set()

    for rid, requirement in req_by_id.items():
        if rid not in covered:
            continue

        refs = _source_refs_for_requirement(plan, rid)
        if not any(_matching_source(requirement, ref) for ref in refs):
            findings.append(
                ValidationFinding(
                    code="SOURCE_TRACEABILITY_MISMATCH",
                    severity="error" if requirement.mandatory else "warning",
                    message=(
                        f"Requirement {rid} is covered but none of its generated source references match "
                        f"{requirement.source.document_id} / v{requirement.source.document_version} / section {requirement.source.section_id}."
                    ),
                    requirement_id=rid,
                )
            )

        module = _find_module(plan, rid)
        task = _find_task(plan, rid)
        quiz = _find_quiz(plan, rid)

        if requirement.assessment_required and requirement.mandatory and quiz is None:
            assessment_missing.add(rid)
            findings.append(
                ValidationFinding(
                    code="ASSESSMENT_MISSING",
                    severity="error",
                    message=f"Requirement {rid} requires an assessment but no quiz item is mapped to it.",
                    requirement_id=rid,
                )
            )

        if requirement.due_stage:
            stages = []
            if module:
                stages.append(module.stage)
            if task:
                stages.append(task.due_stage)
            if any(stage != requirement.due_stage for stage in stages):
                due_stage_mismatch.add(rid)
                findings.append(
                    ValidationFinding(
                        code="DUE_STAGE_MISMATCH",
                        severity="error" if requirement.mandatory else "warning",
                        message=f"Requirement {rid} should be staged at '{requirement.due_stage}'. Generated stages: {sorted(set(stages))}.",
                        requirement_id=rid,
                    )
                )

        if requirement.competency:
            generated_competencies = []
            if module and module.competency:
                generated_competencies.append(module.competency)
            if task and task.competency:
                generated_competencies.append(task.competency)
            if quiz and quiz.competency:
                generated_competencies.append(quiz.competency)
            if not generated_competencies or any(c != requirement.competency for c in generated_competencies):
                findings.append(
                    ValidationFinding(
                        code="COMPETENCY_MISMATCH",
                        severity="error" if requirement.mandatory else "warning",
                        message=f"Requirement {rid} expects competency '{requirement.competency}'.",
                        requirement_id=rid,
                    )
                )

        if module:
            missing_fields = []
            if not module.learning_objectives:
                missing_fields.append("learning_objectives")
            if not module.key_concepts:
                missing_fields.append("key_concepts")
            if not module.assessment:
                missing_fields.append("assessment")
            if not module.completion_criteria:
                missing_fields.append("completion_criteria")
            if missing_fields:
                findings.append(
                    ValidationFinding(
                        code="MODULE_INCOMPLETE",
                        severity="error",
                        message=f"Module {module.module_id} is missing: {', '.join(missing_fields)}.",
                        requirement_id=rid,
                    )
                )

        if task and (not task.description or not task.expected_outcome or not task.completion_criteria):
            findings.append(
                ValidationFinding(
                    code="TASK_CHECKLIST_INCOMPLETE",
                    severity="error",
                    message=f"Task {task.task_id} is missing required completion/checklist content.",
                    requirement_id=rid,
                )
            )

        # Detect explicit conflict/precedence language in cited evidence.
        for ref in refs:
            source_text = source_index.source_text(ref, trusted_only=True).lower()
            if "takes precedence" in source_text or "where faq text conflicts" in source_text:
                contradiction_ids.add(rid)
                findings.append(
                    ValidationFinding(
                        code="SOURCE_CONFLICT",
                        severity="error",
                        message=f"Cited source evidence contains an explicit policy/FAQ conflict for requirement {rid}; precedence must be resolved before verification.",
                        requirement_id=rid,
                    )
                )
                break

    total = len(mandatory)
    covered_mandatory = len(mandatory & covered)
    coverage = round((covered_mandatory / total * 100) if total else 100.0, 2)

    traceable_mandatory = 0
    for rid in mandatory:
        if rid not in covered:
            continue
        requirement = req_by_id[rid]
        if any(_matching_source(requirement, ref) for ref in _source_refs_for_requirement(plan, rid)):
            traceable_mandatory += 1
    traceability = round((traceable_mandatory / covered_mandatory * 100) if covered_mandatory else 100.0, 2)

    errors = [f for f in findings if f.severity == "error"]
    codes = {f.code for f in errors}
    if "SOURCE_CONFLICT" in codes:
        status = "Contradictory"
    elif "PROMPT_INJECTION_SOURCE" in codes or "UNSUPPORTED_REQUIREMENT" in codes:
        status = "Unsupported"
    elif errors:
        status = "Incomplete" if missing or assessment_missing else "Manual Review Required"
    elif findings:
        status = "Verified with Warning"
    else:
        status = "Verified"

    return ValidationResult(
        status=status,
        coverage_score=coverage,
        traceability_score=traceability,
        mandatory_total=total,
        mandatory_covered=covered_mandatory,
        missing_requirement_ids=sorted(missing),
        unsupported_requirement_ids=sorted(unknown),
        duplicate_requirement_ids=sorted(duplicates),
        findings=findings,
        invalid_source_ids=sorted(invalid_source_ids),
        outdated_source_ids=sorted(outdated_source_ids),
        assessment_missing_requirement_ids=sorted(assessment_missing),
        due_stage_mismatch_ids=sorted(due_stage_mismatch),
        contradiction_requirement_ids=sorted(contradiction_ids),
        prompt_injection_source_ids=sorted(prompt_injection_source_ids),
    )
