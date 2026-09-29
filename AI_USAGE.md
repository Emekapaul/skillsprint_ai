# AI Usage Declaration

This project uses AI tools during development in accordance with the competition rules.

| Tool | Purpose | File/module affected | Modification | Test |
|---|---|---|---|---|
| ChatGPT | Architecture, scaffolding, code review, test design, documentation | Project-wide | Team reviews/adapts generated material | Automated tests + manual review |
| Approved GenAI API | Structured onboarding content generation | `app/services/genai_pipeline.py` | Prompt/schema controlled by application | Schema + ground-truth validation |

Before submission, add the team member who reviewed each change and keep this file aligned with actual development activity.

## 2026-09-27 — React + Flask architecture migration

- **AI tool:** ChatGPT
- **Purpose:** Convert the initial Streamlit prototype architecture into a React + Flask full-stack architecture while preserving the independent Python validation pipeline.
- **Assistance type:** Project architecture, API scaffolding, frontend scaffolding, CSS/UI structure, development commands, and test scaffolding.
- **Files/modules affected:** `app.py`, `backend/api.py`, `backend/__init__.py`, `frontend/*`, `requirements.txt`, `README.md`, `docs/ARCHITECTURE_V2.md`, `tests/test_api.py`, `.gitignore`.
- **Modification performed:** Replaced Streamlit as the primary UI entry point with a Flask REST API and React/Vite frontend. Existing Python document-processing, requirement, GenAI, validation, and comparison services remain the business-logic layer.
- **Test performed:** Python compilation completed. Full automated tests require Flask and other dependencies to be installed in the development virtual environment. Frontend build requires `npm install`.
- **Verifying team member:** Team member to review, run, debug, and approve each affected module before submission.
