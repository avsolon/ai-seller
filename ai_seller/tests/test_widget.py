"""Structured AgentResponse conversion tests (doc 13)."""

from app.ai.agent.response import AgentResponse, build_response


def test_build_response_maps_products_from_tools():
    result = {
        "reply": "Для вашего авто подойдёт NEPTUN.",
        "stage": "PRODUCT_SELECTION",
        "handoff": False,
        "tools": [
            {
                "tool": "search_products",
                "success": True,
                "result": {
                    "products": [
                        {
                            "product_id": "p1",
                            "sku": "ORION-1",
                            "name": "ORIONLIGHT NEPTUN 3",
                            "price": 10900,
                            "stock_quantity": 5,
                        }
                    ]
                },
            }
        ],
        "decision": {"required_slots": ["headlight_type"]},
    }
    response: AgentResponse = build_response(result)
    assert response.stage == "PRODUCT_SELECTION"
    assert len(response.products) == 1
    product = response.products[0]
    assert product["price"] == 10900
    assert product["availability"]["status"] == "in_stock"
    assert any(q["id"] == "xenon" for q in response.quick_replies)


def test_build_response_out_of_stock():
    result = {
        "reply": "Пока нет в наличии.",
        "stage": None,
        "handoff": False,
        "tools": [
            {
                "tool": "search_products",
                "success": True,
                "result": {"products": [{"name": "X", "price": 1, "stock_quantity": 0}]},
            }
        ],
        "decision": {"required_slots": []},
    }
    response = build_response(result)
    assert response.products[0]["availability"]["status"] == "out_of_stock"


def test_build_response_empty_tools():
    result = {"reply": "Здравствуйте!", "stage": "DISCOVERY", "handoff": False,
              "tools": [], "decision": {}}
    response = build_response(result)
    assert response.products == []
    assert response.text == "Здравствуйте!"
    assert response.stage == "DISCOVERY"
