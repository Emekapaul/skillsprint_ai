from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.services.document_processor import process_document
PACK = ROOT / "nexasphere_company_pack"


def main() -> None:
    documents = sorted((PACK / "documents").glob("*.docx"))
    rows = list(csv.DictReader((PACK / "role_requirement_matrix.csv").open(encoding="utf-8")))
    roles = {row["role"] for row in rows}
    mandatory = sum(row["mandatory"].strip().lower() == "true" for row in rows)

    adversarial = process_document(
        str(PACK / "documents" / "ADV-001_Prompt_Injection_Test.docx"),
        "ADV-001",
        None,
    )
    flags = sum(bool(chunk.get("prompt_injection_flags")) for chunk in adversarial["chunks"])

    print(f"documents={len(documents)}")
    print(f"roles={len(roles)}")
    print(f"requirements={len(rows)}")
    print(f"mandatory={mandatory}")
    print(f"adversarial_prompt_injection_flags={flags}")

    assert len(documents) == 22
    assert len(roles) == 10
    assert len(rows) == 160
    assert mandatory == 120
    assert flags >= 1
    print("dataset verification: OK")


if __name__ == "__main__":
    main()
