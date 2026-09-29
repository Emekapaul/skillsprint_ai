# Evaluator Demo Path

1. Launch the Flask API and React frontend.
2. Upload approved PDF/DOCX company documents. Leave version as `auto` to use document metadata.
3. Open **Requirement Matrix** and build the selected role's matrix.
4. For the supplied NexaSphere pack, the independent 160-row ground-truth matrix is used; the UI shows the 16 rows for the selected role.
5. Generate with the deterministic Demo Provider to demonstrate repeatability, or with the configured approved GenAI provider.
6. Run **Python Verification**. The validator independently checks mandatory coverage, source traceability, source version, assessments, competency, due stage, checklists, unsupported IDs and prompt-injection/conflict findings.
7. Open **AI ↔ Python** to inspect requirement-level comparison.
8. Upload `ADV-001` and observe the prompt-injection flag. The flagged source is not forwarded to the GenAI provider.
9. Upload a newer version of an existing document. The previous version is retained as obsolete and policy impact analysis identifies changed sections and affected ground-truth requirements where available.
10. Use unseen PDF/DOCX documents without changing application code; when no supplied ground-truth matrix exists for a role, the source-derived candidate matrix path is used.
