from dataclasses import dataclass
from uuid import uuid4


@dataclass(frozen=True)
class MockProviderResult:
    provider_request_id: str
    provider_response_id: str
    request_summary: dict
    response_summary: dict


class MockRechargeProvider:
    provider = "mock_meta"

    def execute_recharge(
        self,
        *,
        recharge_id: str,
        amount: str,
        currency: str,
    ) -> MockProviderResult:
        provider_request_id = f"mock-request:{uuid4()}"
        provider_response_id = f"mock-response:{uuid4()}"
        return MockProviderResult(
            provider_request_id=provider_request_id,
            provider_response_id=provider_response_id,
            request_summary={
                "recharge_id": recharge_id,
                "amount": amount,
                "currency": currency,
            },
            response_summary={"status": "succeeded"},
        )
