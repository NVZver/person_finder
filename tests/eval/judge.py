"""A Groq-backed DeepEval judge model.

DeepEval's LLM-as-judge metrics (`GEval`, faithfulness, etc.) default to
OpenAI. This project only carries a Groq key, so we wrap `ChatGroq` in the
`DeepEvalBaseLLM` interface and hand it to the metrics explicitly.

`GEval` calls `generate_with_schema(prompt, schema=<pydantic model>)` and
prefers a schema *instance* back (it then reads fields directly, skipping
fragile JSON-string parsing). We satisfy that via ChatGroq's
`with_structured_output`, so the judge returns the populated schema object.
"""

from __future__ import annotations

from typing import Any

from deepeval.models import DeepEvalBaseLLM
from langchain_groq import ChatGroq

# A capable judge: scoring factual correctness needs broad world knowledge and
# reliable structured output, which the 8B instant model does not provide.
JUDGE_MODEL = "llama-3.3-70b-versatile"


class GroqJudge(DeepEvalBaseLLM):
    """Adapts `ChatGroq` to DeepEval's judge-model interface."""

    def __init__(self, api_key: str, model: str = JUDGE_MODEL) -> None:
        self._model_name = model
        self._api_key = api_key
        super().__init__(model)

    def load_model(self) -> ChatGroq:
        return ChatGroq(
            model=self._model_name,
            api_key=self._api_key,
            temperature=0,
            # Eval infrastructure (not the production CLI): a small retry
            # budget lets the judge ride out free-tier TPM throttling so the
            # suite stays green when agent + judge calls stack in one minute.
            max_retries=3,
        )

    def generate(self, prompt: str, schema: Any | None = None) -> Any:
        # `self.model` is set by the base __init__ via load_model().
        if schema is not None:
            structured = self.model.with_structured_output(schema)
            return structured.invoke(prompt)
        return self.model.invoke(prompt).content

    async def a_generate(self, prompt: str, schema: Any | None = None) -> Any:
        if schema is not None:
            structured = self.model.with_structured_output(schema)
            return await structured.ainvoke(prompt)
        reply = await self.model.ainvoke(prompt)
        return reply.content

    def get_model_name(self) -> str:
        return f"groq:{self._model_name}"
