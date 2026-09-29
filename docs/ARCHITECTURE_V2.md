# SkillSprint AI v2 Architecture

## Stack

- **React + TypeScript + Vite:** presentation layer
- **Flask:** REST API and orchestration layer
- **Python services:** document processing, source indexing, requirement mapping, GenAI generation, deterministic validation, comparison, policy impact
- **SQLite:** persistent local state; PostgreSQL-ready data model

## Two-pipeline boundary

React never implements business validation rules.

### Pipeline A — generation

1. React requests a role matrix.
2. Flask loads the independent Role Requirement Matrix when available; otherwise it derives source-backed candidate requirements from uploaded documents.
3. Only trusted source chunks are sent to the GenAI provider. Chunks flagged for prompt injection are excluded from generation context.
4. GenAI returns strict structured JSON matching `OnboardingPlan`.

### Pipeline B — independent verification

1. Flask loads the stored role matrix and approved source index.
2. Python validation checks coverage, source document/version/section, assessment mapping, competency, due stage, checklist completeness, duplicate coverage, unsupported IDs, prompt-injection citations and explicit source conflicts.
3. The validator never calls the GenAI provider.
4. Final status is `Verified` only when mandatory requirements are covered and no blocking validation findings remain.

## Source intelligence

PDF and DOCX ingestion preserves:

- document ID
- document version
- effective date when present
- document type when present
- active/obsolete status
- file hash
- section ID
- heading
- page/paragraph/table location
- chunk ID
- prompt-injection flags

DOCX numbered headings such as `5. Escalation` are represented as section `5`, rather than synthetic paragraph IDs. This keeps citations compatible with the role matrix.

## Ground truth

`nexasphere_company_pack/role_requirement_matrix.csv` is treated as the independent ground-truth dataset for the supplied NexaSphere benchmark. It is loaded into `RoleRequirement` records and mapped into generation-facing `Requirement` records without changing the authoritative CSV.

The application still supports source-derived candidate matrices for unseen roles/datasets where no external ground-truth CSV is available.

## Persistence

SQLite stores:

- document versions
- role matrices
- generated plans
- validation results

Uploading a newer document version marks the previous version obsolete while retaining it for audit history.

## Security

Uploaded documents are data, not instructions. Prompt-injection patterns are detected during ingestion, retained for auditability, and excluded from the GenAI source context.
