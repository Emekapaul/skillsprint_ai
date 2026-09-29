from __future__ import annotations

import csv
from pathlib import Path

from app.models.schemas import RoleRequirement


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MATRIX_FILE = PROJECT_ROOT / "nexasphere_company_pack" / "role_requirement_matrix.csv"


def load_ground_truth(path: Path = MATRIX_FILE) -> list[RoleRequirement]:
    requirements: list[RoleRequirement] = []
    with open(path, "r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {
            "requirement_id", "role", "department", "policy_requirement",
            "process_requirement", "competency", "mandatory", "priority",
            "source_document_id", "source_section_id", "assessment_required", "due_stage",
        }
        missing = required - set(reader.fieldnames or [])
        if missing:
            raise ValueError(f"Ground-truth matrix is missing columns: {sorted(missing)}")

        for row in reader:
            requirements.append(
                RoleRequirement(
                    requirement_id=row["requirement_id"].strip(),
                    role=row["role"].strip(),
                    department=row["department"].strip(),
                    policy_requirement=row["policy_requirement"].strip(),
                    process_requirement=row["process_requirement"].strip(),
                    competency=row["competency"].strip(),
                    mandatory=row["mandatory"].strip().lower() == "true",
                    priority=row["priority"].strip(),
                    source_document_id=row["source_document_id"].strip(),
                    source_section_id=row["source_section_id"].strip(),
                    assessment_required=row["assessment_required"].strip().lower() == "true",
                    due_stage=row["due_stage"].strip(),
                )
            )
    return requirements


def requirements_for_role(role: str, path: Path = MATRIX_FILE) -> list[RoleRequirement]:
    target = role.strip().casefold()
    return [r for r in load_ground_truth(path) if r.role.casefold() == target]


def ground_truth_roles(path: Path = MATRIX_FILE) -> list[str]:
    seen: list[str] = []
    for requirement in load_ground_truth(path):
        if requirement.role not in seen:
            seen.append(requirement.role)
    return seen
