"""Tests for the sales state machine."""

from decimal import Decimal

import pytest

from app.ai.sales import (
    SalesStage,
    determine_next_stage,
    funnel_order,
    missing_slots,
    next_question,
)
from app.ai.sales.guard import ResponseGuard
from app.ai.sales.state import NeedState, SalesState, VehicleState
from app.ai.sales.taxonomy import CustomerEmotion, CustomerIntent, SalesStage as StageEnum


def make_state(**overrides) -> SalesState:
    data = {
        "conversation_id": "conv-test",
        "vehicle": VehicleState(),
        "need": NeedState(),
    }
    data.update(overrides)
    return SalesState(**data)


class TestDetermineNextStage:
    def test_new_state_goes_to_discovery(self):
        state = make_state(stage=StageEnum.NEW)
        assert determine_next_stage(state) == SalesStage.DISCOVERY

    def test_handoff_wins(self):
        state = make_state(stage=StageEnum.OBJECTION)
        state.handoff_requested = True
        assert determine_next_stage(state) == SalesStage.HANDOFF

    def test_order_wins(self):
        state = make_state(stage=StageEnum.CLOSING)
        state.purchase.order_created = True
        assert determine_next_stage(state) == SalesStage.ORDER

    def test_ready_to_buy_closing(self):
        state = make_state(stage=StageEnum.PRODUCT_SELECTION)
        state.purchase.ready_to_buy = True
        assert determine_next_stage(state) == SalesStage.CLOSING

    def test_objection_state(self):
        state = make_state(stage=StageEnum.PRODUCT_SELECTION)
        state.add_objection("PRICE", "Дорого")
        assert determine_next_stage(state) == SalesStage.OBJECTION

    def test_identified_vehicle_needs_qualification(self):
        state = make_state(
            vehicle=VehicleState(make="BMW", model="X5", year=2015),
            need=NeedState(primary_need="лучший свет"),
        )
        assert determine_next_stage(state) == SalesStage.VEHICLE_QUALIFICATION

    def test_verified_then_product_selection(self):
        vehicle = VehicleState(make="BMW", model="X5", year=2015)
        vehicle.compatibility_verified = True
        state = make_state(vehicle=vehicle, need=NeedState(primary_need="дальний свет"))
        assert determine_next_stage(state) == SalesStage.PRODUCT_SELECTION


class TestMissingSlots:
    def test_empty_asks_vehicle_first(self):
        state = make_state()
        slots = missing_slots(state)
        assert slots == ["vehicle_make", "vehicle_model", "vehicle_year"]
        assert next_question(state) == "Подскажите марку автомобиля."

    def test_vehicle_known_then_need(self):
        state = make_state(vehicle=VehicleState(make="BMW", model="X5", year=2015))
        assert missing_slots(state)[0] == "primary_need"

    def test_qualification_slots(self):
        state = make_state(
            vehicle=VehicleState(make="BMW", model="X5", year=2015),
            need=NeedState(primary_need="дальний свет"),
        )
        slots = missing_slots(state)
        assert "headlight_type" in slots
        assert "current_lens" in slots

    def test_ready_to_buy_skips_need_questions(self):
        state = make_state(
            vehicle=VehicleState(make="Audi", model="Q5", year=2018),
            need=NeedState(),
        )
        state.purchase.ready_to_buy = True
        assert missing_slots(state) == ["quantity", "installation_mode"]
        assert next_question(state) == "Сколько комплектов нужно?"

    def test_unidentified_vehicle_still_asks_vehicle_first(self):
        state = make_state(need=NeedState())
        state.purchase.ready_to_buy = True
        assert missing_slots(state) == ["vehicle_make", "vehicle_model", "vehicle_year"]


class TestStateSerialization:
    def test_round_trip(self):
        state = make_state(stage=StageEnum.OBJECTION)
        state.intent = CustomerIntent.PRICE_OBJECTION
        state.emotion = CustomerEmotion.SKEPTICAL
        state.need.budget = Decimal("15000")
        state.add_objection("PRICE", "Дорого")
        restored = SalesState.from_dict(state.to_dict())
        assert restored.stage == SalesStage.OBJECTION
        assert restored.intent == CustomerIntent.PRICE_OBJECTION
        assert restored.emotion == CustomerEmotion.SKEPTICAL
        assert restored.need.budget == Decimal("15000")
        assert restored.objections[0].code == "PRICE"
        assert restored.vehicle.make is None

    def test_funnel_has_expected_stages(self):
        order = funnel_order()
        assert order["NEW"] < order["DISCOVERY"]
        assert order["DISCOVERY"] < order["CLOSING"]
        assert order["CLOSING"] < order["ORDER"]


class TestResponseGuard:
    def test_false_compatibility_when_not_verified(self):
        guard = ResponseGuard()
        state = make_state()
        issues = guard.check("Да, эта линза точно подойдёт без переделок.", state)
        assert any(i["code"] == "false_compatibility_claim" for i in issues)

    def test_ok_when_verified(self):
        guard = ResponseGuard()
        vehicle = VehicleState(make="BMW", model="X5", year=2015)
        vehicle.compatibility_verified = True
        state = make_state(vehicle=vehicle)
        issues = guard.check("Для вашей конфигурации совместимость подтверждена.", state)
        assert issues == []

    def test_aggressive_pressure(self):
        guard = ResponseGuard()
        issues = guard.check("Заказывайте прямо сейчас, не упустите выгоду.")
        assert any(i["code"] == "aggressive_pressure" for i in issues)

    def test_too_many_questions(self):
        guard = ResponseGuard()
        issues = guard.check("Какой авто? Какой год? Какой бюджет? Куда доставить?")
        assert any(i["code"] == "too_many_questions" for i in issues)

    def test_normal_reply_clean(self):
        guard = ResponseGuard()
        issues = guard.check("Понимаю. Подскажите, какой сейчас тип фар?")
        assert issues == []
