from datetime import datetime, timezone

from app.models.schemas import Requirement, SourceRef, OnboardingPlan
from app.services.validation_engine import validate_plan


def req(rid="R1", mandatory=True, assessment=True, stage="Day 1"):
    return Requirement(
        requirement_id=rid,
        role="Data Analyst",
        title=rid,
        category="policy",
        mandatory=mandatory,
        priority="High",
        source=SourceRef(
            document_id="DOC-1",
            document_version="1.0",
            section_id="S1",
            location="page:1",
        ),
        requirement_text="Employee must follow the approved requirement.",
        competency="Must Know",
        assessment_required=assessment,
        due_stage=stage,
        origin="ground_truth",
    )


def plan_for(r, with_quiz=True):
    return OnboardingPlan(
        role="Data Analyst",
        employee_id="E1",
        plan_id="P1",
        prompt_version="v1",
        model_name="demo",
        generated_at=datetime.now(timezone.utc).isoformat(),
        modules=[{
            "module_id": "M1",
            "module_title": r.title,
            "purpose": "x",
            "learning_objectives": ["x"],
            "key_concepts": ["x"],
            "required_sources": [r.source],
            "estimated_duration_minutes": 10,
            "assessment": "x",
            "completion_criteria": "x",
            "requirement_ids": [r.requirement_id],
            "stage": r.due_stage,
            "competency": r.competency,
        }],
        tasks=[{
            "task_id": "T1",
            "description": "x",
            "expected_outcome": "x",
            "source": r.source,
            "completion_criteria": "x",
            "difficulty": "Beginner",
            "due_stage": r.due_stage,
            "requirement_ids": [r.requirement_id],
            "competency": r.competency,
        }],
        quiz=[{
            "question_id": "Q1",
            "question_type": "true_false",
            "question": "x",
            "options": ["True", "False"],
            "correct_answer": ["True"],
            "explanation": "x",
            "difficulty": "Beginner",
            "source": r.source,
            "requirement_id": r.requirement_id,
            "competency": r.competency,
        }] if with_quiz else [],
    )


def test_full_coverage():
    r = req()
    v = validate_plan(plan_for(r), [r], [{"document_id": "DOC-1", "version": "1.0", "status": "active", "chunks": [{"document_id": "DOC-1", "version": "1.0", "section_id": "S1", "location": "page:1", "text": "approved", "prompt_injection_flags": []}]}])
    assert v.coverage_score == 100
    assert v.traceability_score == 100
    assert v.status == "Verified"


def test_missing_requirement():
    r = req()
    plan = OnboardingPlan(
        role="Data Analyst", employee_id="E1", plan_id="P1", prompt_version="v1", model_name="demo",
        generated_at=datetime.now(timezone.utc).isoformat(), modules=[], tasks=[], quiz=[]
    )
    v = validate_plan(plan, [r], {"DOC-1": "1.0"})
    assert v.coverage_score == 0
    assert "R1" in v.missing_requirement_ids


def test_missing_required_assessment_is_incomplete():
    r = req(assessment=True)
    v = validate_plan(plan_for(r, with_quiz=False), [r], {"DOC-1": "1.0"})
    assert "R1" in v.assessment_missing_requirement_ids
    assert v.status == "Incomplete"
