from app.agents.interfaces import StructuredLLMRequest, StructuredLLMResult


class FakeStructuredLLMClient:
    def __init__(
        self,
        *,
        response: dict[str, object],
        model_name: str = "fake-structured-model",
    ) -> None:
        self.response = response
        self.model_name = model_name

    def generate_json(self, request: StructuredLLMRequest) -> StructuredLLMResult:
        return StructuredLLMResult(
            content=dict(self.response),
            model_provider="fake",
            model_name=request.model_name or self.model_name,
            prompt_version=request.prompt_version,
            request_id="fake-request",
            usage={"prompt_tokens": 0, "completion_tokens": 0},
            raw_text=None,
        )
