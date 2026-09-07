"""Intent detector tests: taxonomy sanity + sales_rag_eval regression."""

from app.ai.agent.intent_detector import detect, extract_facts
from app.ai.sales import evaluation
from app.ai.sales.taxonomy import CustomerIntent


class TestIntentDetector:
    def test_detects_greeting(self):
        assert detect("Здравствуйте!") == CustomerIntent.GREETING

    def test_detects_price_objection(self):
        assert detect("Дорого, на Авито дешевле") == CustomerIntent.PRICE_OBJECTION

    def test_detects_vehicle_info(self):
        assert detect("У меня BMW X5 2015, ксенон") == CustomerIntent.VEHICLE_INFO

    def test_detects_order(self):
        assert detect("Давайте оформим заказ") == CustomerIntent.ORDER_REQUEST

    def test_extracts_facts(self):
        facts = extract_facts("BMW X5 2015, ксенон, хочу свет лучше, бюджет до 15000")
        assert facts["vehicle_make"] == "Bmw"
        assert facts["vehicle_year"] == 2015
        assert facts["headlight_type"] == "xenon"
        assert facts["budget"] == 15000


class TestEvalRegression:
    def test_intents_match_eval_dataset(self):
        cases = evaluation.load_cases()
        report = evaluation.run_eval(cases, lambda case: detect(case.input))
        assert report["failed"] == 0
        assert report["accuracy"] == 1.0
