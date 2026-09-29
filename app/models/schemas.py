from typing import List, Optional, Literal

from pydantic import BaseModel, ConfigDict, Field


Status = Literal[
    "Verified",
    "Verified with Warning",
    "Incomplete",
    "Unsupported",
    "Contradictory",
    "Manual Review Required",
]


class SourceRef(BaseModel):
    document_id: str
    document_version: str
    section_id: str
    location: str


class Requirement(BaseModel):
    requirement_id: str
    role: str
    title: str
    category: Literal["policy", "process", "competency", "task", "assessment"]
    mandatory: bool
    priority: Literal["High", "Medium", "Low"]
    source: SourceRef
    requirement_text: str
    assessment_topic: Optional[str] = None
    prerequisite_ids: List[str] = Field(default_factory=list)

    # Ground-truth fields are populated when a role matrix row is available.
    # They remain optional for source-derived matrices on unseen documents.
    department: Optional[str] = None
    policy_requirement: Optional[str] = None
    process_requirement: Optional[str] = None
    competency: Optional[str] = None
    assessment_required: Optional[bool] = None
    due_stage: Optional[str] = None
    origin: Literal["ground_truth", "source_extracted"] = "source_extracted"


class RoleRequirement(BaseModel):
    requirement_id: str
    role: str
    department: str
    policy_requirement: str
    process_requirement: str
    competency: str
    mandatory: bool
    priority: Literal["High", "Medium", "Low"]
    source_document_id: str
    source_section_id: str
    assessment_required: bool
    due_stage: str


class Module(BaseModel):
    module_id: str
    module_title: str
    purpose: str
    learning_objectives: List[str]
    key_concepts: List[str]
    required_sources: List[SourceRef]
    estimated_duration_minutes: int
    assessment: str
    completion_criteria: str
    requirement_ids: List[str]
    stage: Literal["Day 1", "Week 1", "Week 2", "First 30 Days", "First 60 Days", "First 90 Days"]
    competency: Optional[str] = None


class Task(BaseModel):
    task_id: str
    description: str
    expected_outcome: str
    source: SourceRef
    completion_criteria: str
    difficulty: Literal["Beginner", "Intermediate", "Advanced"]
    due_stage: str
    requirement_ids: List[str]
    competency: Optional[str] = None


class QuizQuestion(BaseModel):
    question_id: str
    question_type: Literal["multiple_choice", "multiple_response", "true_false", "scenario"]
    question: str
    options: List[str]
    correct_answer: List[str]
    explanation: str
    difficulty: Literal["Beginner", "Intermediate", "Advanced"]
    source: SourceRef
    requirement_id: str
    competency: Optional[str] = None


class OnboardingPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: str
    employee_id: str
    plan_id: str
    prompt_version: str
    model_name: str
    generated_at: str
    modules: List[Module]
    tasks: List[Task]
    quiz: List[QuizQuestion]


class ValidationFinding(BaseModel):
    code: str
    severity: Literal["error", "warning", "info"]
    message: str
    requirement_id: Optional[str] = None


class ValidationResult(BaseModel):
    status: Status
    coverage_score: float
    traceability_score: float
    mandatory_total: int
    mandatory_covered: int
    missing_requirement_ids: List[str]
    unsupported_requirement_ids: List[str]
    duplicate_requirement_ids: List[str]
    findings: List[ValidationFinding]
    invalid_source_ids: List[str] = Field(default_factory=list)
    outdated_source_ids: List[str] = Field(default_factory=list)
    assessment_missing_requirement_ids: List[str] = Field(default_factory=list)
    due_stage_mismatch_ids: List[str] = Field(default_factory=list)
    contradiction_requirement_ids: List[str] = Field(default_factory=list)
    prompt_injection_source_ids: List[str] = Field(default_factory=list)


class ComparisonRow(BaseModel):
    requirement_id: str
    role: str
    python_expected: bool
    genai_present: bool
    match: bool
    source_valid: bool
    validation_status: str
