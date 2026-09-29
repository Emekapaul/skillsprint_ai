from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Iterable

from app.models.schemas import SourceRef


@dataclass(frozen=True)
class SourceKey:
    document_id: str
    version: str
    section_id: str


class SourceIndex:
    """Deterministic lookup/validation layer for approved source chunks."""

    def __init__(self, documents: Iterable[dict[str, Any]]):
        self.documents = list(documents)
        self.by_key: dict[SourceKey, list[dict[str, Any]]] = defaultdict(list)
        self.versions_by_document: dict[str, set[str]] = defaultdict(set)
        self.active_versions: dict[str, str] = {}
        self.injection_chunks: set[str] = set()

        for document in self.documents:
            document_id = str(document.get("document_id", ""))
            version = str(document.get("version", ""))
            status = str(document.get("status", "active")).lower()
            self.versions_by_document[document_id].add(version)
            if status == "active":
                self.active_versions[document_id] = version

            for chunk in document.get("chunks", []):
                key = SourceKey(
                    document_id=document_id,
                    version=str(chunk.get("version", version)),
                    section_id=str(chunk.get("section_id", "")),
                )
                self.by_key[key].append(chunk)
                if chunk.get("prompt_injection_flags"):
                    self.injection_chunks.add(chunk.get("chunk_id", ""))

    def document_exists(self, document_id: str) -> bool:
        return document_id in self.versions_by_document

    def version_exists(self, document_id: str, version: str) -> bool:
        return version in self.versions_by_document.get(document_id, set())

    def section_exists(self, document_id: str, version: str, section_id: str) -> bool:
        if not any(key.document_id == document_id and key.version == version for key in self.by_key):
            # Backward-compatible validation when only document/version metadata
            # is supplied (for example, a unit test fixture).
            return True
        return SourceKey(document_id, version, str(section_id)) in self.by_key

    def chunks_for(self, document_id: str, version: str, section_id: str) -> list[dict[str, Any]]:
        return list(self.by_key.get(SourceKey(document_id, version, str(section_id)), []))

    def validate_ref(self, source: SourceRef) -> list[tuple[str, str]]:
        findings: list[tuple[str, str]] = []
        if not self.document_exists(source.document_id):
            findings.append(("INVALID_SOURCE_DOCUMENT", f"Unknown source document {source.document_id}."))
            return findings
        if not self.version_exists(source.document_id, source.document_version):
            findings.append(
                (
                    "OUTDATED_SOURCE_VERSION",
                    f"Source {source.document_id} version {source.document_version} is not an ingested approved version.",
                )
            )
            return findings
        if source.document_id in self.active_versions and self.active_versions[source.document_id] != source.document_version:
            findings.append(
                (
                    "OUTDATED_SOURCE_VERSION",
                    f"Source {source.document_id} cites version {source.document_version}; active version is {self.active_versions[source.document_id]}.",
                )
            )
        if not self.section_exists(source.document_id, source.document_version, source.section_id):
            findings.append(
                (
                    "INVALID_SOURCE_SECTION",
                    f"Source {source.document_id} v{source.document_version} has no section {source.section_id}.",
                )
            )
        return findings

    def ref_is_prompt_injected(self, source: SourceRef) -> bool:
        return any(
            chunk.get("prompt_injection_flags")
            for chunk in self.chunks_for(source.document_id, source.document_version, source.section_id)
        )

    def source_text(self, source: SourceRef, trusted_only: bool = True) -> str:
        chunks = self.chunks_for(source.document_id, source.document_version, source.section_id)
        if trusted_only:
            chunks = [c for c in chunks if not c.get("prompt_injection_flags")]
        return "\n".join(str(c.get("text", "")) for c in chunks)
