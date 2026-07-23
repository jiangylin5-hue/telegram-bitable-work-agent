from scripts.stage09_first_workspace_provisioning import (
    ProvisioningTargetError,
    build_provisioning_receipt,
    parse_single_private_target,
)


def test_parse_single_private_target_accepts_one_matching_allowlisted_private_user() -> None:
    assert parse_single_private_target(
        [
            {
                "telegram_user_id": "123456",
                "telegram_chat_id": "123456",
                "raw_text": "/stage07-bind",
                "message_type": "text",
            }
        ]
    ) == {"telegram_user_id": "123456", "telegram_chat_id": "123456"}


def test_parse_single_private_target_rejects_missing_mismatched_or_multiple_values() -> None:
    for candidates in (
        [],
        [{"telegram_user_id": "123", "telegram_chat_id": "456", "raw_text": "/stage07-bind", "message_type": "text"}],
        [
            {"telegram_user_id": "123", "telegram_chat_id": "123", "raw_text": "/stage07-bind", "message_type": "text"},
            {"telegram_user_id": "456", "telegram_chat_id": "456", "raw_text": "/stage07-bind", "message_type": "text"},
        ],
    ):
        try:
            parse_single_private_target(candidates)
        except ProvisioningTargetError as exc:
            assert str(exc) == "single_matching_private_target_required"
        else:
            raise AssertionError("expected a safe provisioning refusal")


def test_provisioning_receipt_never_contains_raw_telegram_values() -> None:
    receipt = build_provisioning_receipt(
        status="created",
        workspace_id="workspace-1",
        base_id="base-1",
        table_count=3,
        has_binding=True,
    )

    assert receipt == {
        "status": "created",
        "workspace_id": "workspace-1",
        "base_id": "base-1",
        "table_count": 3,
        "has_binding": True,
    }
    assert "123456" not in str(receipt)
