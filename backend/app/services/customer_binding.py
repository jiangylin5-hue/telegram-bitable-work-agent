from dataclasses import dataclass
from typing import Any, Protocol


@dataclass
class TelegramCustomerBindingRecord:
    customer_id: Any
    telegram_chat_id: str | None
    telegram_user_id: str | None
    binding_scope: str
    status: str = "active"
    id: Any | None = None
    label: str | None = None
    created_by: str | None = None


@dataclass(frozen=True)
class CustomerBindingResolution:
    binding_status: str
    customer_id: Any | None = None
    binding_id: Any | None = None
    binding_scope: str | None = None


class CustomerBindingLookup(Protocol):
    def list_customer_bindings(
        self,
        *,
        telegram_chat_id: str,
        telegram_user_id: str | None,
    ) -> list[TelegramCustomerBindingRecord]:
        pass


def resolve_customer_binding(
    lookup: CustomerBindingLookup,
    *,
    telegram_chat_id: str,
    telegram_user_id: str | None,
) -> CustomerBindingResolution:
    bindings = [
        binding
        for binding in lookup.list_customer_bindings(
            telegram_chat_id=telegram_chat_id,
            telegram_user_id=telegram_user_id,
        )
        if binding.status == "active"
    ]
    for scope in ("chat_user", "chat", "user"):
        matches = [
            binding
            for binding in bindings
            if _matches_scope(
                binding,
                scope=scope,
                telegram_chat_id=telegram_chat_id,
                telegram_user_id=telegram_user_id,
            )
        ]
        if len(matches) > 1:
            return CustomerBindingResolution(binding_status="binding_conflict")
        if len(matches) == 1:
            binding = matches[0]
            return CustomerBindingResolution(
                binding_status="bound",
                customer_id=binding.customer_id,
                binding_id=binding.id,
                binding_scope=binding.binding_scope,
            )
    return CustomerBindingResolution(binding_status="needs_manual_binding")


def _matches_scope(
    binding: TelegramCustomerBindingRecord,
    *,
    scope: str,
    telegram_chat_id: str,
    telegram_user_id: str | None,
) -> bool:
    if binding.binding_scope != scope:
        return False
    if scope == "chat_user":
        return (
            telegram_user_id is not None
            and binding.telegram_chat_id == telegram_chat_id
            and binding.telegram_user_id == telegram_user_id
        )
    if scope == "chat":
        return binding.telegram_chat_id == telegram_chat_id
    if scope == "user":
        return telegram_user_id is not None and binding.telegram_user_id == telegram_user_id
    return False
