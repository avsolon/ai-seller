"""Tests for taxonomy + evaluation dataset consistency."""

from app.ai.sales import evaluation, taxonomy
from app.ai.sales.taxonomy import (
    SalesStage,
    funnel_stages,
    is_valid_intent,
    load_taxonomy,
    taxonomy_exists,
)


class TestTaxonomy:
    def test_taxonomy_file_exists(self):
        assert taxonomy_exists()

    def test_funnel_matches_code(self):
        funnel = funnel_stages()
        assert funnel == [s.value for s in SalesStage]
        assert len(set(funnel)) == len(funnel)

    def test_intents_known(self):
        data = load_taxonomy()
        intents = data.get("customer_intents", {})
        assert intents
        for code in intents:
            assert is_valid_intent(code)

    def test_discovery_slots_have_required(self):
        slots = taxonomy.discovery_slots()
        assert slots["vehicle_make"]["required"] is True
        assert slots["primary_need"]["required"] is True
        assert slots["headlight_type"]["required"] is False


class TestEvaluation:
    def test_eval_dataset_loads(self):
        cases = evaluation.load_cases()
        assert len(cases) >= 20
        ids = [c.id for c in cases]
        assert len(ids) == len(set(ids))

    def test_eval_intents_all_valid(self):
        cases = evaluation.load_cases()
        invalid = evaluation.validate_cases(cases)
        assert invalid == []

    def test_run_eval_with_perfect_classifier(self):
        cases = evaluation.load_cases()

        def perfect(case):
            return case.expected_intent

        report = evaluation.run_eval(cases, perfect)
        assert report["passed"] == report["total"]
        assert report["accuracy"] == 1.0

    def test_run_eval_reports_failures(self):
        cases = evaluation.load_cases()

        def wrong(case):
            return None

        report = evaluation.run_eval(cases, wrong)
        assert report["failed"] == report["total"]
        assert report["accuracy"] == 0.0
