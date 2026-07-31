from scripts.stage12_gold_review_manifest import build_gold_review_manifest


def test_gold_review_manifest_exposes_all_human_approved_truth() -> None:
    manifest = build_gold_review_manifest()

    assert manifest["version"] == "stage12-gold-review-manifest.v1"
    assert manifest["status"] == "human_approved"
    assert manifest["case_count"] == 48
    assert manifest["human_approved_count"] == 48
    assert len(manifest["cases"]) == 48
    assert len({item["case_id"] for item in manifest["cases"]}) == 48
    assert all(
        item["current_audit_status"] == "human_approved" for item in manifest["cases"]
    )
    assert all(
        {
            "query",
            "evaluation_clock",
            "objectives",
            "predicates",
            "required_result_records",
            "allowed_evidence_records",
            "forbidden_result_records",
            "relation_paths",
            "aggregates",
            "actions",
            "fixture_source_records",
            "fixture_source_relations",
            "audit_review",
            "source_fixture_hash",
            "v2_case_hash",
        }.issubset(item)
        for item in manifest["cases"]
    )
    assert all(
        item["evaluation_clock"] == "2026-07-29T00:00:00+08:00"
        for item in manifest["cases"]
    )
    assert all(
        item["audit_review"]["review_method"] == "manual_source_audit"
        for item in manifest["cases"]
    )
    by_id = {item["case_id"]: item for item in manifest["cases"]}
    assert {
        (item["table_key"], item["record_id"])
        for item in by_id["join_01"]["fixture_source_records"]
    } == {
        ("projects", "PRJ-ATLAS"),
        ("work_items", "MT-001"),
        ("work_items", "MT-002"),
        ("work_items", "MT-003"),
        ("risks", "RISK-001"),
        ("risks", "RISK-002"),
        ("risks", "RISK-003"),
    }
    assert {
        (item["source"], item["field"], item["target"])
        for item in by_id["join_01"]["fixture_source_relations"]
    } >= {
        ("MT-001", "work_items.project_link", "PRJ-ATLAS"),
        ("RISK-001", "risks.affected_work_items", "MT-001"),
    }
    assert by_id["task_02"]["evaluation_clock"].startswith("2026-07-29")
    assert by_id["task_02"]["actions"][0]["assignments"]["due_date"] == ("2026-07-29")
    assert manifest["fixture_source"]["snapshot_hash"] == manifest["fixture_hash"]
    assert manifest["manifest_hash"]
