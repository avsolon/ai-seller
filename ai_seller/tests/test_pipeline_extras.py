"""Ingestion validation, prompt messages and LLM retry policy tests."""

import asyncio
from pathlib import Path

from app.ai.llm.manager import _is_retryable
from app.ai.prompts.prompt_builder import PromptBuilder
from rag.embeddings import sales_dataset

DATASET_DIR = Path("rag/seller_dialogues")


def test_all_dataset_records_are_valid():
    total = 0
    problems = 0
    for path in sorted(DATASET_DIR.glob("*.jsonl")):
        for record in sales_dataset.iter_dataset(path):
            total += 1
            errors = sales_dataset.validate_record(record)
            problems += len(errors)
    assert total > 100
    assert problems == 0


def test_build_payload_for_dataset_records():
    sample = None
    for path in DATASET_DIR.glob("sales_rag_dataset.jsonl"):
        for record in sales_dataset.iter_dataset(path):
            sample = record
            break
    assert sample is not None
    payload = sales_dataset.build_payload(sample, "default-shop")
    assert payload["label"] in ("positive", "negative")
    assert payload["intent"]
    assert payload["sales_stage"]


class TestPromptMessages:
    def test_build_messages_returns_system_context_history(self):
        async def run():
            builder = PromptBuilder()
            messages = await builder.build_messages(
                state={"stage": "OBJECTION", "intent": "PRICE_OBJECTION"},
                rag_context={
                    "sales_patterns": [
                        {
                            "label": "positive",
                            "dialogue": [
                                {"role": "customer", "text": "Дорого"},
                                {"role": "seller", "text": "Понимаю ваш вопрос."},
                            ],
                            "successful_strategy": ["acknowledge_objection"],
                        }
                    ]
                },
                tool_context=[{"tool": "get_price", "result": {"price": 10900}}],
                history=[{"role": "user", "content": "Дорого"}],
            )
            assert messages[0].role == "system"
            assert "CURRENT SALES STATE" in messages[1].content
            assert "SALES KNOWLEDGE" in messages[1].content
            assert "VERIFIED BUSINESS DATA" in messages[1].content
            assert messages[-1].role == "user"

        asyncio.run(run())


class TestLLMRetryPolicy:
    def test_retryable_infra_errors(self):
        assert _is_retryable(TimeoutError("timeout")) is True
        assert _is_retryable(ConnectionError("connection refused")) is True
        assert _is_retryable(RuntimeError("gigachat error: 503 Service Unavailable")) is True
        assert _is_retryable(RuntimeError("rate limit exceeded 429")) is True

    def test_non_retryable_errors_are_not_masked(self):
        assert _is_retryable(ValueError("invalid prompt schema")) is False
        assert _is_retryable(RuntimeError("invalid_api_key")) is False
