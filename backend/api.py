from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

from app.db.database import (
    init_db,
    load_documents,
    load_matrices,
    load_plans,
    save_document,
    save_matrix,
    save_plan,
    save_validation,
)
from app.models.schemas import SourceRef
from app.services.comparison_engine import compare
from app.services.document_processor import process_document
from app.services.genai_pipeline import DemoProvider, OpenAIProvider
from app.services.ground_truth import ground_truth_roles
from app.services.matrix_service import build_role_matrix
from app.services.policy_impact import impact_analysis
from app.services.source_index import SourceIndex
from app.services.validation_engine import validate_plan

load_dotenv()

ROOT = Path(__file__).resolve().parents[1]
UPLOAD_DIR = ROOT / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 20 * 1024 * 1024
CORS(app, resources={r"/api/*": {"origins": os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")}})

init_db()


def _load_role_catalog() -> list[dict[str, str]]:
    path = ROOT / "nexasphere_company_pack" / "roles.json"
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


ROLE_CATALOG = _load_role_catalog()
ROLE_NAMES = [item["role"] for item in ROLE_CATALOG] or ground_truth_roles()

STATE: dict[str, Any] = {
    "documents": load_documents(),
    "matrix": load_matrices(),
    "plans": {},
    "validations": {},
}
loaded_plans, loaded_validations = load_plans()
STATE["plans"].update(loaded_plans)
STATE["validations"].update(loaded_validations)


def json_error(message: str, status: int = 400):
    return jsonify({"error": message}), status


def serialize(value: Any):
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [serialize(v) for v in value]
    if isinstance(value, dict):
        return {k: serialize(v) for k, v in value.items()}
    return value


def all_documents() -> list[dict]:
    return list(STATE["documents"].values())


def active_documents() -> list[dict]:
    return [d for d in all_documents() if d.get("status", "active") == "active"]


def all_chunks() -> list[dict]:
    return [chunk for doc in active_documents() for chunk in doc.get("chunks", [])]


def role_department(role: str) -> str:
    for item in ROLE_CATALOG:
        if item.get("role") == role:
            return item.get("department", "")
    return ""


@app.get("/api/health")
def health():
    return jsonify({"status": "ok", "service": "skillsprint-ai-api", "persistence": "sqlite"})


@app.get("/api/roles")
def roles():
    return jsonify({"roles": ROLE_NAMES})


@app.get("/api/documents")
def documents():
    rows = []
    for doc in all_documents():
        rows.append(
            {
                "document_id": doc["document_id"],
                "title": doc.get("title"),
                "filename": doc.get("filename"),
                "file_type": doc.get("file_type"),
                "document_type": doc.get("document_type"),
                "version": doc.get("version"),
                "effective_date": doc.get("effective_date"),
                "status": doc.get("status", "active"),
                "file_hash": doc.get("file_hash"),
                "page_count": doc.get("page_count", 0),
                "source_parts": doc.get("source_parts", 0),
                "chunks": len(doc.get("chunks", [])),
                "prompt_injection_flags": sum(bool(c.get("prompt_injection_flags")) for c in doc.get("chunks", [])),
            }
        )
    return jsonify({"documents": rows})


@app.get("/api/documents/<document_id>")
def document_detail(document_id: str):
    matches = [d for d in all_documents() if d.get("document_id") == document_id]
    if not matches:
        return json_error(f"Document '{document_id}' was not found.", 404)
    active = next((d for d in matches if d.get("status") == "active"), matches[-1])
    return jsonify(
        {
            "document": {
                "document_id": active["document_id"],
                "title": active.get("title"),
                "filename": active.get("filename"),
                "file_type": active.get("file_type"),
                "document_type": active.get("document_type"),
                "version": active.get("version"),
                "effective_date": active.get("effective_date"),
                "status": active.get("status", "active"),
                "file_hash": active.get("file_hash"),
                "page_count": active.get("page_count", 0),
                "source_parts": active.get("source_parts", 0),
                "chunks": active.get("chunks", []),
                "versions": [
                    {"version": d.get("version"), "status": d.get("status", "active")} for d in matches
                ],
            }
        }
    )


@app.post("/api/documents/upload")
def upload_documents():
    files = request.files.getlist("files")
    if not files:
        return json_error("No PDF or DOCX files were uploaded.")

    version_input = (request.form.get("version") or "").strip()
    version_override = None if version_input.lower() in {"", "auto"} else version_input
    processed_rows = []

    for file in files:
        if not file.filename:
            continue
        ext = Path(file.filename).suffix.lower()
        if ext not in {".pdf", ".docx"}:
            return json_error(f"Unsupported file type: {file.filename}. Only PDF and DOCX are supported.")

        original_stem = Path(file.filename).stem
        id_match = re.match(r"^([A-Za-z]+-\d+)", original_stem)
        document_id = id_match.group(1).upper() if id_match else "DOC-" + re.sub(r"[^A-Z0-9]+", "-", original_stem.upper())[:24].strip("-")

        safe_version = re.sub(r"[^A-Za-z0-9._-]+", "-", version_override or "auto")
        destination = UPLOAD_DIR / f"{document_id}_v{safe_version}{ext}"
        file.save(destination)

        try:
            processed = process_document(str(destination), document_id, version_override)
        except Exception as exc:
            return json_error(f"Could not process {file.filename}: {exc}", 422)

        processed["title"] = original_stem
        processed["filename"] = file.filename
        STATE["documents"][f"{processed['document_id']}::{processed['version']}"] = processed
        save_document(processed)

        processed_rows.append(
            {
                "document_id": processed["document_id"],
                "title": processed.get("title"),
                "filename": processed.get("filename"),
                "file_type": processed.get("file_type"),
                "document_type": processed.get("document_type"),
                "version": processed.get("version"),
                "effective_date": processed.get("effective_date"),
                "status": processed.get("status", "active"),
                "file_hash": processed.get("file_hash"),
                "page_count": processed.get("page_count", 0),
                "source_parts": processed.get("source_parts", 0),
                "chunks": len(processed.get("chunks", [])),
                "prompt_injection_flags": sum(bool(c.get("prompt_injection_flags")) for c in processed.get("chunks", [])),
            }
        )

    return jsonify({"documents": processed_rows}), 201


@app.post("/api/matrix/build")
def build_requirement_matrix():
    payload = request.get_json(silent=True) or {}
    role = payload.get("role")
    if not role:
        return json_error("role is required")
    chunks = all_chunks()
    if not chunks:
        return json_error("Upload at least one document before building the matrix.")

    matrix, origin = build_role_matrix(role, chunks)
    STATE["matrix"][role] = matrix
    save_matrix(role, matrix, origin)
    return jsonify({"role": role, "origin": origin, "requirements": serialize(matrix), "count": len(matrix)})


@app.get("/api/matrix")
def get_matrix():
    role = request.args.get("role")
    if not role:
        return jsonify({"matrices": {k: serialize(v) for k, v in STATE["matrix"].items()}})
    return jsonify({"role": role, "requirements": serialize(STATE["matrix"].get(role, []))})


@app.get("/api/ground-truth/summary")
def ground_truth_summary():
    rows = []
    for role in ROLE_NAMES:
        matrix = STATE["matrix"].get(role, [])
        rows.append(
            {
                "role": role,
                "mapped": len(matrix),
                "mandatory": sum(r.mandatory for r in matrix),
                "origin": "ground_truth" if any(r.origin == "ground_truth" for r in matrix) else "source_extracted",
            }
        )
    return jsonify({"roles": rows})


@app.get("/api/source/lookup")
def source_lookup():
    document_id = request.args.get("document_id")
    version = request.args.get("version")
    section_id = request.args.get("section_id")
    if not document_id or not version or not section_id:
        return json_error("document_id, version and section_id are required")
    index = SourceIndex(active_documents())
    source = SourceRef(
        document_id=document_id,
        document_version=version,
        section_id=section_id,
        location=f"section:{section_id}",
    )
    return jsonify(
        {
            "document_id": document_id,
            "version": version,
            "section_id": section_id,
            "valid": not index.validate_ref(source),
            "text": index.source_text(source, trusted_only=True),
        }
    )


@app.post("/api/onboarding/generate")
def generate_onboarding():
    payload = request.get_json(silent=True) or {}
    role = payload.get("role")
    employee = payload.get("employee") or {}
    provider_name = payload.get("provider", "demo")
    if not role:
        return json_error("role is required")
    requirements = STATE["matrix"].get(role)
    if not requirements:
        return json_error("Build the Role Requirement Matrix for this role first.")

    employee.setdefault("employee_id", "EMP-001")
    employee.setdefault("name", "Demo Employee")
    employee.setdefault("role", role)
    employee.setdefault("department", role_department(role))
    employee.setdefault("experience_level", "Intermediate")
    employee.setdefault("joining_date", "2026-09-27")

    try:
        provider = OpenAIProvider() if provider_name == "openai" else DemoProvider()
        plan = provider.generate(employee, requirements, all_chunks())
    except Exception as exc:
        return json_error(f"Generation failed: {exc}", 502)

    STATE["plans"][plan.plan_id] = plan
    STATE["validations"].pop(plan.plan_id, None)
    save_plan(plan)
    return jsonify({"plan": serialize(plan)})


@app.post("/api/onboarding/validate")
def validate_onboarding():
    payload = request.get_json(silent=True) or {}
    plan_id = payload.get("plan_id")
    if not plan_id or plan_id not in STATE["plans"]:
        return json_error("A valid plan_id is required.")
    plan = STATE["plans"][plan_id]
    requirements = STATE["matrix"].get(plan.role, [])
    if not requirements:
        return json_error("No requirement matrix is stored for this plan's role.")
    index = SourceIndex(active_documents())
    result = validate_plan(plan, requirements, active_documents(), source_index=index)
    STATE["validations"][plan_id] = result
    save_validation(plan_id, result)
    return jsonify({"validation": serialize(result)})


@app.get("/api/onboarding/comparison")
def onboarding_comparison():
    plan_id = request.args.get("plan_id")
    if not plan_id or plan_id not in STATE["plans"]:
        return json_error("A valid plan_id is required.")
    plan = STATE["plans"][plan_id]
    requirements = STATE["matrix"].get(plan.role, [])
    index = SourceIndex(active_documents())
    rows = compare(plan, requirements, index)
    return jsonify({"rows": serialize(rows), "count": len(rows)})


@app.post("/api/policy/impact")
def policy_impact():
    payload = request.get_json(silent=True) or {}
    document_id = payload.get("document_id")
    if not document_id:
        return json_error("document_id is required")
    versions = [d for d in all_documents() if d.get("document_id") == document_id]
    if not versions:
        return json_error(f"Document '{document_id}' was not found.", 404)
    active = next((d for d in versions if d.get("status") == "active"), versions[-1])
    return jsonify(impact_analysis(versions, active))


@app.get("/api/dashboard")
def dashboard():
    docs = all_documents()
    return jsonify(
        {
            "documents": len(docs),
            "active_documents": len(active_documents()),
            "obsolete_documents": sum(d.get("status") == "obsolete" for d in docs),
            "roles": len(STATE["matrix"]),
            "requirements": sum(len(v) for v in STATE["matrix"].values()),
            "plans": len(STATE["plans"]),
            "validated_plans": len(STATE["validations"]),
        }
    )


if __name__ == "__main__":
    # app.run(host="127.0.0.1", port=int(os.getenv("PORT", "5000")), debug=True)
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=True)
