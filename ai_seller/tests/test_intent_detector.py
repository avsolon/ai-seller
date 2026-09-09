"""Intent detector tests: taxonomy sanity + sales_rag_eval regression."""

from app.ai.agent.intent_detector import detect, extract_facts, is_purchase_selection
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

    def test_extracts_need_from_free_answers(self):
        assert extract_facts("яркость")["primary_need"] == "яркость"
        assert extract_facts("дальность")["primary_need"] == "дальний свет"
        assert extract_facts("все сразу")["primary_need"] == "все сразу"
        assert extract_facts("ширину света")["primary_need"] == "ширина света"
        assert extract_facts("и яркость и дальность")["primary_need"] == "дальний свет и яркость"

    def test_recommendation_variants(self):
        assert detect("из вашего наличия предложите") == CustomerIntent.PRODUCT_RECOMMENDATION
        assert detect("предложи что-нибудь") == CustomerIntent.PRODUCT_RECOMMENDATION
        assert detect("подбери вариант") == CustomerIntent.PRODUCT_RECOMMENDATION

    def test_extracts_current_lens(self):
        assert extract_facts("штатные")["current_lens"] == "factory"
        assert extract_facts("родные стоят")["current_lens"] == "factory"
        assert extract_facts("не убирал ничего!")["current_lens"] == "factory"
        assert extract_facts("уже стоят би-лед модули")["current_lens"] == "aftermarket"
        assert extract_facts("не родные, меняли на би-лед")["current_lens"] == "aftermarket"
        assert extract_facts("стоит не родной, колхоз")["current_lens"] == "aftermarket"

    def test_future_replacement_not_aftermarket(self):
        assert extract_facts("хочу поставить би-лед модули").get("current_lens") is None
        assert extract_facts("хочу заменить штатную оптику")["current_lens"] == "factory"

    def test_detects_compare_wording(self):
        assert detect("чем отличаются светодиодные линзы от билед модулей") \
            == CustomerIntent.PRODUCT_COMPARISON


class TestPurchaseSelection:
    def test_selects_offered_variant(self):
        assert is_purchase_selection("первый вариант")
        assert is_purchase_selection("второй вариант")
        assert is_purchase_selection("этот модуль")
        assert is_purchase_selection("данные линзы")

    def test_verb_plus_model_token(self):
        assert is_purchase_selection("выбираю NEPTUN")
        assert is_purchase_selection("мне понравился pluton")
        assert is_purchase_selection("остановлюсь на vega")

    def test_question_phrasing_never_selection(self):
        assert not is_purchase_selection("сколько стоит первый вариант?")
        assert not is_purchase_selection("какой вариант подойдёт?")
        assert not is_purchase_selection("можно первый вариант?")
        assert not is_purchase_selection("чем отличается второй вариант?")
        assert not is_purchase_selection("первый вариант встанет на мою машину?")

    def test_buy_verbs_handled_by_detect(self):
        assert detect("беру pluton") == CustomerIntent.PURCHASE_INTENT

    def test_pure_selection_detect_returns_none_then_upgrades(self):
        assert detect("первый вариант") is None
        assert is_purchase_selection("первый вариант")

    def test_non_selection(self):
        assert not is_purchase_selection("")
        assert not is_purchase_selection("нужны фары посветлее")
        assert not is_purchase_selection("что-нибудь подешевле")
        assert not is_purchase_selection("подбери вариант")


class TestEvalRegression:
    def test_intents_match_eval_dataset(self):
        cases = evaluation.load_cases()
        report = evaluation.run_eval(cases, lambda case: detect(case.input))
        assert report["failed"] == 0
        assert report["accuracy"] == 1.0
