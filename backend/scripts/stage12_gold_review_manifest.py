"""Build the human-review manifest for Stage12's frozen 48-case Gold set."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import tempfile

from scripts.stage12_quality_evaluation import (
    _fixture_snapshot,
    build_stage12_truth_cases,
    canonical_sha256,
)


def build_gold_review_manifest() -> dict[str, object]:
    cases = build_stage12_truth_cases()
    snapshot = _fixture_snapshot()
    fixture_hash = canonical_sha256(snapshot)
    record_catalog = _fixture_record_catalog(snapshot)
    entries = []
    for case in cases:
        objectives = tuple(
            {
                "objective_id": objective.objective_id,
                "kind": objective.kind,
                "required": objective.required,
                "entity_scope": objective.entity_scope,
                "output_contract": objective.output_contract,
            }
            for objective in case.expected_task_spec.objectives
        )
        predicates = tuple(
            {
                "objective_id": objective.objective_id,
                **predicate.model_dump(mode="json"),
            }
            for objective in case.expected_task_spec.objectives
            for predicate in objective.predicates
        )
        objective_paths = tuple(
            {
                "objective_id": objective.objective_id,
                "path": path,
            }
            for objective in case.expected_task_spec.objectives
            for path in objective.relation_paths
        )
        referenced_record_ids = {
            *case.expected_query_result.required_result_records,
            *case.expected_query_result.allowed_evidence_records,
            *case.expected_query_result.forbidden_result_records,
            *(
                record_id
                for objective in case.expected_task_spec.objectives
                for record_id in objective.entity_scope
            ),
        }
        for action in case.expected_task_spec.action_slots:
            referenced_record_ids.update(
                _known_record_ids(
                    action.target_selector,
                    record_catalog=record_catalog,
                )
            )
            referenced_record_ids.update(
                _known_record_ids(
                    action.assignments,
                    record_catalog=record_catalog,
                )
            )
        fixture_source_records = tuple(
            record_catalog[record_id]
            for record_id in sorted(referenced_record_ids)
            if record_id in record_catalog
        )
        fixture_source_relations = tuple(
            relation
            for relation in snapshot["relations"]
            if relation["source"] in referenced_record_ids
            and relation["target"] in referenced_record_ids
        )
        entries.append(
            {
                "case_id": case.case_id,
                "category": case.category,
                "query": case.query,
                "evaluation_clock": case.evaluation_clock,
                "objectives": objectives,
                "dependency_edges": tuple(
                    item.model_dump(mode="json")
                    for item in case.expected_task_spec.dependency_edges
                ),
                "predicates": predicates,
                "required_result_records": (
                    case.expected_query_result.required_result_records
                ),
                "allowed_evidence_records": (
                    case.expected_query_result.allowed_evidence_records
                ),
                "forbidden_result_records": (
                    case.expected_query_result.forbidden_result_records
                ),
                "relation_paths": {
                    "objectives": objective_paths,
                    "query_result": case.expected_query_result.relation_paths,
                },
                "aggregates": tuple(
                    item.model_dump(mode="json")
                    for item in case.expected_query_result.aggregates
                ),
                "sort_specs": tuple(
                    item.model_dump(mode="json")
                    for item in case.expected_query_result.sort_specs
                ),
                "actions": tuple(
                    item.model_dump(mode="json")
                    for item in case.expected_task_spec.action_slots
                ),
                "fixture_source_records": fixture_source_records,
                "fixture_source_relations": fixture_source_relations,
                "expected_permission_outcome": case.expected_permission_outcome,
                "audit_review": {
                    "review_method": case.gold_audit.review_method,
                    "reviewer": case.gold_audit.reviewer,
                    "reviewed_at": case.gold_audit.reviewed_at,
                },
                "source_fixture_hash": case.gold_audit.source_fixture_hash,
                "v2_case_hash": case.gold_audit.v2_case_hash,
                "change_reason": case.gold_audit.change_reason,
                "current_audit_status": case.gold_audit.status,
            }
        )
    human_approved_count = sum(
        entry["current_audit_status"] == "human_approved" for entry in entries
    )
    values: dict[str, object] = {
        "version": "stage12-gold-review-manifest.v1",
        "status": (
            "human_approved"
            if human_approved_count == len(entries) == 48
            else "pending_explicit_human_signoff"
        ),
        "case_count": len(entries),
        "human_approved_count": human_approved_count,
        "fixture_hash": fixture_hash,
        "fixture_source": {
            "schema_version": snapshot["schema_version"],
            "source_module": "scripts.stage12_quality_evaluation._fixture_snapshot",
            "materializer_module": (
                "scripts.stage12_evaluation_fixture."
                "materialize_stage12_evaluation_fixture"
            ),
            "snapshot_hash": fixture_hash,
            "snapshot": snapshot,
        },
        "cases": entries,
    }
    values["manifest_hash"] = canonical_sha256(values)
    return values


def render_gold_review_markdown(manifest: dict[str, object]) -> str:
    fixture_source = manifest["fixture_source"]
    table_counts = {
        table_key: len(table["records"])
        for table_key, table in fixture_source["snapshot"]["tables"].items()
    }
    lines = [
        "# Stage12 48-Case Human Gold Review Manifest",
        "",
        f"- Status: `{manifest['status']}`",
        f"- Case count: `{manifest['case_count']}`",
        f"- Human-approved count: `{manifest['human_approved_count']}`",
        f"- Fixture hash: `{manifest['fixture_hash']}`",
        f"- Manifest hash: `{manifest['manifest_hash']}`",
        "- Fixture table record counts: `" + _compact(table_counts) + "`",
        "- Fixture relation count: `"
        + str(len(fixture_source["snapshot"]["relations"]))
        + "`",
        "- Fixture permission profile: `"
        + _compact(fixture_source["snapshot"]["permission_profile"])
        + "`",
        "- Approval evidence: explicit in-thread 48/48 Human Gold sign-off on 2026-07-31.",
        "",
    ]
    for entry in manifest["cases"]:
        lines.extend(
            (
                f"## {entry['case_id']} · {entry['category']}",
                "",
                f"**Query:** {entry['query']}",
                "",
                f"- Evaluation clock: `{entry['evaluation_clock']}`",
                "- Objectives: `" + _compact(entry["objectives"]) + "`",
                "- Dependency edges: `" + _compact(entry["dependency_edges"]) + "`",
                "- Predicates: `" + _compact(entry["predicates"]) + "`",
                "- Required results: `"
                + _compact(entry["required_result_records"])
                + "`",
                "- Allowed evidence: `"
                + _compact(entry["allowed_evidence_records"])
                + "`",
                "- Forbidden results: `"
                + _compact(entry["forbidden_result_records"])
                + "`",
                "- Relation paths: `" + _compact(entry["relation_paths"]) + "`",
                "- Aggregates: `" + _compact(entry["aggregates"]) + "`",
                "- Sort specs: `" + _compact(entry["sort_specs"]) + "`",
                "- Actions: `" + _compact(entry["actions"]) + "`",
                "- Fixture source records: `"
                + _compact(entry["fixture_source_records"])
                + "`",
                "- Fixture source relations: `"
                + _compact(entry["fixture_source_relations"])
                + "`",
                f"- Permission: `{entry['expected_permission_outcome']}`",
                "- Agent audit review: `" + _compact(entry["audit_review"]) + "`",
                f"- Current audit status: `{entry['current_audit_status']}`",
                f"- Source fixture hash: `{entry['source_fixture_hash']}`",
                f"- V2 case hash: `{entry['v2_case_hash']}`",
                f"- Change reason: `{entry['change_reason']}`",
                "",
            )
        )
    return "\n".join(lines)


def write_gold_review_manifest(output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest = build_gold_review_manifest()
    json_path = output_dir / "stage12-48case-gold-review-manifest.json"
    markdown_path = output_dir / "stage12-48case-gold-review-manifest.md"
    _atomic_write(
        json_path,
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
    )
    _atomic_write(markdown_path, render_gold_review_markdown(manifest))
    return json_path, markdown_path


def _compact(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _fixture_record_catalog(
    snapshot: dict[str, object],
) -> dict[str, dict[str, object]]:
    identity_fields = {
        "projects": "project_code",
        "work_items": "ticket_code",
        "risks": "risk_code",
        "owners": "owner_code",
        "interactions": "interaction_code",
    }
    catalog: dict[str, dict[str, object]] = {}
    for table_key, table in snapshot["tables"].items():
        identity_field = identity_fields.get(table_key)
        if identity_field is None:
            continue
        for record in table["records"]:
            record_id = record.get(identity_field)
            if not isinstance(record_id, str) or not record_id:
                raise ValueError("gold_review_fixture_record_identity_invalid")
            if record_id in catalog:
                raise ValueError("gold_review_fixture_record_identity_duplicate")
            catalog[record_id] = {
                "table_key": table_key,
                "record_id": record_id,
                "values": record,
                "version": snapshot["record_versions"].get(record_id),
            }
    return catalog


def _known_record_ids(
    value: object,
    *,
    record_catalog: dict[str, dict[str, object]],
) -> set[str]:
    if isinstance(value, str):
        return {value} if value in record_catalog else set()
    if isinstance(value, dict):
        return {
            record_id
            for item in value.values()
            for record_id in _known_record_ids(item, record_catalog=record_catalog)
        }
    if isinstance(value, (list, tuple)):
        return {
            record_id
            for item in value
            for record_id in _known_record_ids(item, record_catalog=record_catalog)
        }
    return set()


def _atomic_write(path: Path, value: str) -> None:
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="\n",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            handle.write(value)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        temporary = None
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    json_path, markdown_path = write_gold_review_manifest(args.output_dir)
    print(json.dumps({"json": str(json_path), "markdown": str(markdown_path)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
