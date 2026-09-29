from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from app.models.schemas import OnboardingPlan, Requirement


class GenAIProvider:
    def generate(
        self,
        employee: dict,
        requirements: list[Requirement],
        sources: list[dict],
    ) -> OnboardingPlan:
        raise NotImplementedError


def trusted_sources_for_requirements(requirements: list[Requirement], sources: list[dict]) -> list[dict]:
    """Return only source excerpts referenced by the matrix and free of prompt-injection flags."""
    wanted = {
        (r.source.document_id, r.source.document_version, str(r.source.section_id))
        for r in requirements
    }
    selected = []
    for source in sources:
        key = (
            source.get("document_id"),
            str(source.get("version")),
            str(source.get("section_id")),
        )
        if key not in wanted:
            continue
        if source.get("prompt_injection_flags"):
            continue
        selected.append(source)
    return selected


class DemoProvider(GenAIProvider):
    """Deterministic provider used for demos/tests; it is driven by the supplied matrix."""

    def generate(self, employee, requirements, sources):
        role = employee["role"]
        mandatory = [r for r in requirements if r.mandatory]
        modules = []
        tasks = []
        quiz = []

        for i, requirement in enumerate(mandatory, 1):
            source = requirement.source
            stage = requirement.due_stage or "Day 1"
            competency = requirement.competency or requirement.assessment_topic
            modules.append(
                {
                    "module_id": f"M-{i:03d}",
                    "module_title": requirement.title,
                    "purpose": f"Build role readiness for: {requirement.title}",
                    "learning_objectives": [
                        f"Explain the approved requirement for {role}",
                        f"Apply the requirement at the {competency or 'required'} level",
                    ],
                    "key_concepts": [requirement.requirement_text[:240]],
                    "required_sources": [source.model_dump()],
                    "estimated_duration_minutes": 15,
                    "assessment": f"Demonstrate understanding of {requirement.title}",
                    "completion_criteria": "Complete the module and satisfy the documented completion criteria.",
                    "requirement_ids": [requirement.requirement_id],
                    "stage": stage,
                    "competency": competency,
                }
            )
            tasks.append(
                {
                    "task_id": f"T-{i:03d}",
                    "description": f"Perform a supervised practice activity for: {requirement.title}",
                    "expected_outcome": requirement.process_requirement or "Employee demonstrates the documented procedure.",
                    "source": source.model_dump(),
                    "completion_criteria": "Manager confirms the documented steps were followed.",
                    "difficulty": "Beginner" if i <= 3 else "Intermediate",
                    "due_stage": stage,
                    "requirement_ids": [requirement.requirement_id],
                    "competency": competency,
                }
            )
            if requirement.assessment_required is not False:
                quiz.append(
                    {
                        "question_id": f"Q-{i:03d}",
                        "question_type": "true_false",
                        "question": f"True or False: The employee must follow the approved requirement '{requirement.title}'.",
                        "options": ["True", "False"],
                        "correct_answer": ["True"],
                        "explanation": "The answer is derived from the mandatory requirement in the approved source matrix.",
                        "difficulty": "Beginner",
                        "source": source.model_dump(),
                        "requirement_id": requirement.requirement_id,
                        "competency": competency,
                    }
                )

        return OnboardingPlan(
            role=role,
            employee_id=employee["employee_id"],
            plan_id=f"PLAN-{employee['employee_id']}",
            prompt_version="onboarding_v1",
            model_name="demo-provider",
            generated_at=datetime.now(timezone.utc).isoformat(),
            modules=modules,
            tasks=tasks,
            quiz=quiz,
        )


class OpenAIProvider(GenAIProvider):
    def __init__(self, model: str | None = None):
        from openai import OpenAI

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")
        self.client = OpenAI(api_key=api_key)
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-5.6-luna")

    def generate(self, employee, requirements, sources):
        schema = OnboardingPlan.model_json_schema()
        prompt_path = Path(__file__).resolve().parents[1] / "prompts" / "onboarding_v1.txt"
        prompt = prompt_path.read_text(encoding="utf-8")
        safe_sources = trusted_sources_for_requirements(requirements, sources)
        req_text = json.dumps([r.model_dump() for r in requirements], ensure_ascii=False, indent=2)
        src_text = json.dumps(safe_sources, ensure_ascii=False, indent=2)
        rendered = prompt.format(
            employee=json.dumps(employee, ensure_ascii=False),
            requirements=req_text,
            sources=src_text,
        )
        response = self.client.responses.create(
            model=self.model,
            input=rendered,
            text={
                "format": {
                    "type": "json_schema",
                    "name": "onboarding_plan",
                    "schema": schema,
                    "strict": True,
                }
            },
        )
        data = json.loads(response.output_text)
        return OnboardingPlan.model_validate(data)
