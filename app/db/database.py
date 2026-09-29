from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from typing import Any

from app.models.schemas import OnboardingPlan, Requirement, ValidationResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "skillsprint.db"


def db_path() -> str:
    return os.getenv("DATABASE_PATH", str(DEFAULT_DB_PATH))


def connect(path: str | None = None):
    target = Path(path or db_path())
    target.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(target)
    con.row_factory = sqlite3.Row
    return con


def _table_columns(con, table: str) -> set[str]:
    return {row[1] for row in con.execute(f"PRAGMA table_info({table})").fetchall()}


def _migrate_documents_table(con) -> None:
    columns = _table_columns(con, "documents")
    if not columns or "document_key" in columns:
        return

    con.execute("ALTER TABLE documents RENAME TO documents_legacy")
    con.execute(
        """
        CREATE TABLE documents (
          document_key TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          title TEXT,
          version TEXT NOT NULL,
          effective_date TEXT,
          category TEXT,
          status TEXT NOT NULL DEFAULT 'active',
          content_json TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    legacy_columns = _table_columns(con, "documents_legacy")
    if {"document_id", "version", "content_json"}.issubset(legacy_columns):
        rows = con.execute("SELECT document_id, title, version, effective_date, category, content_json FROM documents_legacy").fetchall()
        for row in rows:
            key = f"{row['document_id']}::{row['version']}"
            try:
                payload = json.loads(row["content_json"] or "{}")
            except json.JSONDecodeError:
                payload = {}
            payload.setdefault("document_id", row["document_id"])
            payload.setdefault("title", row["title"])
            payload.setdefault("version", row["version"])
            payload.setdefault("effective_date", row["effective_date"])
            payload.setdefault("document_type", row["category"])
            payload.setdefault("status", "active")
            con.execute(
                "INSERT OR IGNORE INTO documents(document_key, document_id, title, version, effective_date, category, status, content_json) VALUES(?,?,?,?,?,?,?,?)",
                (key, row["document_id"], row["title"], row["version"], row["effective_date"], row["category"], "active", json.dumps(payload, ensure_ascii=False)),
            )
    con.execute("DROP TABLE documents_legacy")


def init_db(path: str | None = None) -> None:
    con = connect(path)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS employees (
          employee_id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          role TEXT NOT NULL,
          department TEXT,
          experience_level TEXT,
          joining_date TEXT
        );

        CREATE TABLE IF NOT EXISTS documents (
          document_key TEXT PRIMARY KEY,
          document_id TEXT NOT NULL,
          title TEXT,
          version TEXT NOT NULL,
          effective_date TEXT,
          category TEXT,
          status TEXT NOT NULL DEFAULT 'active',
          content_json TEXT NOT NULL,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_documents_id ON documents(document_id);

        CREATE TABLE IF NOT EXISTS matrices (
          role TEXT PRIMARY KEY,
          content_json TEXT NOT NULL,
          origin TEXT NOT NULL,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS plans (
          plan_id TEXT PRIMARY KEY,
          employee_id TEXT,
          role TEXT,
          content_json TEXT NOT NULL,
          validation_json TEXT,
          created_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    _migrate_documents_table(con)
    con.commit()
    con.close()


def save_document(document: dict[str, Any]) -> None:
    key = f"{document['document_id']}::{document['version']}"
    con = connect()
    con.execute(
        "UPDATE documents SET status='obsolete' WHERE document_id=? AND version<>?",
        (document["document_id"], document["version"]),
    )
    con.execute(
        """
        INSERT INTO documents(document_key, document_id, title, version, effective_date, category, status, content_json)
        VALUES(?,?,?,?,?,?,?,?)
        ON CONFLICT(document_key) DO UPDATE SET
          title=excluded.title,
          effective_date=excluded.effective_date,
          category=excluded.category,
          status=excluded.status,
          content_json=excluded.content_json
        """,
        (
            key,
            document["document_id"],
            document.get("title"),
            document["version"],
            document.get("effective_date"),
            document.get("document_type"),
            "active",
            json.dumps(document, ensure_ascii=False),
        ),
    )
    con.commit()
    con.close()


def load_documents() -> dict[str, dict[str, Any]]:
    con = connect()
    rows = con.execute("SELECT document_key, content_json, status FROM documents ORDER BY document_id, version").fetchall()
    con.close()
    result = {}
    for row in rows:
        document = json.loads(row["content_json"])
        document["status"] = row["status"]
        result[row["document_key"]] = document
    return result


def save_matrix(role: str, requirements: list[Requirement], origin: str) -> None:
    con = connect()
    con.execute(
        """
        INSERT INTO matrices(role, content_json, origin)
        VALUES(?,?,?)
        ON CONFLICT(role) DO UPDATE SET content_json=excluded.content_json, origin=excluded.origin, updated_at=CURRENT_TIMESTAMP
        """,
        (role, json.dumps([r.model_dump(mode="json") for r in requirements], ensure_ascii=False), origin),
    )
    con.commit()
    con.close()


def load_matrices() -> dict[str, list[Requirement]]:
    con = connect()
    rows = con.execute("SELECT role, content_json FROM matrices").fetchall()
    con.close()
    return {row["role"]: [Requirement.model_validate(item) for item in json.loads(row["content_json"])] for row in rows}


def save_plan(plan: OnboardingPlan) -> None:
    con = connect()
    con.execute(
        """
        INSERT INTO plans(plan_id, employee_id, role, content_json, validation_json)
        VALUES(?,?,?,?,NULL)
        ON CONFLICT(plan_id) DO UPDATE SET content_json=excluded.content_json, employee_id=excluded.employee_id, role=excluded.role
        """,
        (plan.plan_id, plan.employee_id, plan.role, json.dumps(plan.model_dump(mode="json"), ensure_ascii=False)),
    )
    con.commit()
    con.close()


def save_validation(plan_id: str, validation: ValidationResult) -> None:
    con = connect()
    con.execute("UPDATE plans SET validation_json=? WHERE plan_id=?", (json.dumps(validation.model_dump(mode="json"), ensure_ascii=False), plan_id))
    con.commit()
    con.close()


def load_plans() -> tuple[dict[str, OnboardingPlan], dict[str, ValidationResult]]:
    con = connect()
    rows = con.execute("SELECT plan_id, content_json, validation_json FROM plans").fetchall()
    con.close()
    plans: dict[str, OnboardingPlan] = {}
    validations: dict[str, ValidationResult] = {}
    for row in rows:
        plans[row["plan_id"]] = OnboardingPlan.model_validate(json.loads(row["content_json"]))
        if row["validation_json"]:
            validations[row["plan_id"]] = ValidationResult.model_validate(json.loads(row["validation_json"]))
    return plans, validations
