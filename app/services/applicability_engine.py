import re
from typing import Any


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip().lower()


def tokenize(text: str) -> set[str]:
    text = normalize(text)
    return set(re.findall(r"[a-z0-9]+", text))


# Generic role/domain vocabulary.
#
# This is intentionally based on role semantics rather than
# NexaSphere document IDs.
ROLE_TERMS = {
  "customer experience": {
        "customer",
        "support",
        "ticket",
        "tickets",
        "handling",
        "escalation",
        "response",
        "targets",
        "knowledge",
        "service",
        "verification",
        "records",
    },
    "sales": {
        "sales",
        "lead",
        "leads",
        "opportunity",
        "opportunities",
        "pricing",
        "crm",
        "handover",
        "customer",
    },
    "human resources": {
        "hr",
        "employee",
        "employees",
        "personnel",
        "recruitment",
        "onboarding",
        "leave",
        "attendance",
        "performance",
        "employment",
        "manager",
    },
    "finance": {
        "finance",
        "invoice",
        "invoices",
        "payment",
        "payments",
        "reconciliation",
        "expense",
        "expenses",
        "financial",
        "receipt",
    },
    "operations": {
        "operations",
        "continuity",
        "recovery",
        "escalation",
        "incident",
        "process",
        "workflow",
        "compliance",
    },
    "marketing": {
        "marketing",
        "customer",
        "campaign",
        "communication",
        "brand",
        "privacy",
        "compliance",
    },
    "technology": {
        "software",
        "code",
        "coding",
        "development",
        "testing",
        "deployment",
        "version",
        "secrets",
        "security",
        "device",
    },
    "data & analytics": {
        "data",
        "analysis",
        "analytics",
        "customer",
        "records",
        "quality",
        "reporting",
        "privacy",
        "compliance",
    },
    "information security": {
        "security",
        "password",
        "mfa",
        "access",
        "device",
        "incident",
        "classification",
        "privacy",
        "secrets",
    },
}


def department_for_role(role: str, roles: list[dict[str, Any]]) -> str:
    target = normalize(role)

    for item in roles:
        if normalize(item.get("role", "")) == target:
            return item.get("department", "")

    return ""


def role_terms(
    role: str,
    roles: list[dict[str, Any]],
) -> set[str]:
    terms = set()

    department = department_for_role(role, roles)

    if department:
        terms.update(tokenize(department))
        terms.update(ROLE_TERMS.get(normalize(department), set()))

    normalized_role = normalize(role)

    # Add meaningful words from the role itself.
    role_words = tokenize(normalized_role)
    terms.update(
        word
        for word in role_words
        if len(word) >= 4
    )

    # Match department-specific vocabulary.
    for department_name, vocabulary in ROLE_TERMS.items():
        if normalize(department) == department_name:
            terms.update(vocabulary)

    return terms


def applicability_score(
    role: str,
    section_text: str,
    roles: list[dict[str, Any]],
) -> float:
    """
    Return a generic semantic relevance score between 0 and 1.

    This is NOT the ground-truth answer. It is only evidence
    used to identify candidate source material for a role.
    """

    section_tokens = tokenize(section_text)

    if not section_tokens:
        return 0.0

    terms = role_terms(role, roles)

    if not terms:
        return 0.0

    matches = section_tokens.intersection(terms)

    return len(matches) / max(len(terms), 1)


def is_applicable(
    role: str,
    section_text: str,
    roles: list[dict[str, Any]],
    threshold: float = 0.05,
) -> bool:
    return applicability_score(
        role=role,
        section_text=section_text,
        roles=roles,
    ) >= threshold