"""Script to generate complete Sales RAG Dataset with all categories."""

import json
from pathlib import Path
from typing import Dict, List


def save_dialogues(dialogues: List[Dict], filename: str, output_dir: Path) -> None:
    """Save dialogues to JSONL file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    filepath = output_dir / filename
    with open(filepath, "w", encoding="utf-8") as f:
        for dialogue in dialogues:
            f.write(json.dumps(dialogue, ensure_ascii=False) + "\n")
    print(f"✅ Saved {len(dialogues)} dialogues to {filepath}")


def generate_all_dialogues() -> Dict[str, List[Dict]]:
    """Generate all dialogue categories."""
    
    dialogues = {
        "greeting": [
            {
                "id": "sales_000001",
                "scenario": "greeting",
                "customer_profile": {"type": "newbie", "experience": "none"},
                "sales_stage": "greeting",
                "intent": "greeting",
                "emotion": "neutral",
                "objection": None,
                "goal": "discover_need",
                "dialogue": [
                    {"role": "customer", "text": "Здравствуйте!"},
                    {"role": "seller", "text": "Здравствуйте! Подскажите, для какого автомобиля ищете линзы и что хотите улучшить — яркость, дальность или просто заменить штатную оптику?"}
                ],
                "successful_strategy": ["acknowledge_greeting", "ask_vehicle", "ask_goal"],
                "mistakes_to_avoid": ["immediate_sales_pitch", "ignore_customer"],
                "tags": ["greeting", "need_discovery", "vehicle_qualification"],
                "quality_score": 0.95,
                "language": "ru"
            },
            {
                "id": "sales_000002",
                "scenario": "greeting",
                "customer_profile": {"type": "newbie", "experience": "none"},
                "sales_stage": "greeting",
                "intent": "greeting",
                "emotion": "neutral",
                "objection": None,
                "goal": "discover_need",
                "dialogue": [
                    {"role": "customer", "text": "Добрый день!"},
                    {"role": "seller", "text": "Добрый день! Подбираем светодиодные линзы для замены или строите новый проект?"}
                ],
                "successful_strategy": ["acknowledge_greeting", "ask_project_type", "ask_vehicle"],
                "mistakes_to_avoid": ["too_generic", "ignore_context"],
                "tags": ["greeting", "need_discovery"],
                "quality_score": 0.94,
                "language": "ru"
            }
        ],
        
        "vehicle_qualification": [
            {
                "id": "sales_000020",
                "scenario": "vehicle_qualification",
                "customer_profile": {"type": "newbie", "experience": "none"},
                "sales_stage": "qualification",
                "intent": "vehicle_identification",
                "emotion": "neutral",
                "objection": None,
                "goal": "confirm_vehicle_details",
                "dialogue": [
                    {"role": "customer", "text": "BMW X5 2015 года."},
                    {"role": "seller", "text": "Понял. У X5 этого года могут отличаться варианты фар. Подскажите, у вас обычный галоген, ксенон или уже стоит заводской Bi-LED?"}
                ],
                "successful_strategy": ["acknowledge_vehicle", "ask_headlight_type", "avoid_assumptions"],
                "mistakes_to_avoid": ["assume_configuration", "skip_technical_details"],
                "tags": ["vehicle", "qualification", "technical"],
                "quality_score": 0.98,
                "language": "ru"
            }
        ],
        
        "product_selection": [
            {
                "id": "sales_000030",
                "scenario": "product_selection",
                "customer_profile": {"type": "technical", "experience": "high"},
                "sales_stage": "recommendation",
                "intent": "product_recommendation",
                "emotion": "interested",
                "objection": None,
                "goal": "recommend_suitable_product",
                "dialogue": [
                    {"role": "customer", "text": "Какие линзы подойдут для моего BMW X5 F15?"},
                    {"role": "seller", "text": "Для вашего автомобиля подойдут две модели: OrionLight SATURN 3 дюйма (8900₽) и OrionLight JUPITER 3 дюйма (8900₽). Обе дают отличное соотношение цена/качество. Какую рассматриваете?"}
                ],
                "successful_strategy": ["provide_options", "compare_features", "ask_preference"],
                "mistakes_to_avoid": ["overwhelm_with_choices", "ignore_budget"],
                "tags": ["recommendation", "product_comparison"],
                "quality_score": 0.97,
                "language": "ru"
            }
        ],
        
        "price_objections": [
            {
                "id": "sales_000050",
                "scenario": "price_objection",
                "customer_profile": {"type": "price_sensitive", "experience": "low"},
                "sales_stage": "objection",
                "intent": "price_comparison",
                "emotion": "skeptical",
                "objection": "too_expensive",
                "goal": "understand_budget_and_value",
                "dialogue": [
                    {"role": "customer", "text": "Почему у вас так дорого?"},
                    {"role": "seller", "text": "Понимаю ваш вопрос. Если сравниваете с другими линзами, давайте лучше посмотрим, что именно входит в комплект и какие характеристики для вас важны."}
                ],
                "successful_strategy": ["acknowledge_objection", "do_not_argue", "clarify_comparison", "identify_customer_priority"],
                "mistakes_to_avoid": ["defend_price_immediately", "criticize_competitors", "pressure_customer"],
                "tags": ["price", "objection", "comparison"],
                "quality_score": 0.98,
                "language": "ru"
            }
        ],
        
        "quality_objections": [
            {
                "id": "sales_000070",
                "scenario": "quality_objection",
                "customer_profile": {"type": "skeptical", "experience": "medium"},
                "sales_stage": "objection",
                "intent": "quality_doubt",
                "emotion": "skeptical",
                "objection": "quality_uncertainty",
                "goal": "provide_quality_assurance",
                "dialogue": [
                    {"role": "customer", "text": "А качество нормальное?"},
                    {"role": "seller", "text": "Да, на эту модель гарантия 24 месяца. Вот характеристики: световой поток 12000 люмен, температура 5500K, ресурс 50000 часов. Могу также прислать отзывы клиентов."}
                ],
                "successful_strategy": ["provide_facts", "mention_warranty", "offer_reviews"],
                "mistakes_to_avoid": ["vague_assurance", "overpromise"],
                "tags": ["quality", "objection", "assurance"],
                "quality_score": 0.95,
                "language": "ru"
            }
        ],
        
        "compatibility_objections": [
            {
                "id": "sales_000080",
                "scenario": "compatibility_objection",
                "customer_profile": {"type": "skeptical", "experience": "medium"},
                "sales_stage": "objection",
                "intent": "compatibility_doubt",
                "emotion": "skeptical",
                "objection": "compatibility_uncertainty",
                "goal": "confirm_compatibility",
                "dialogue": [
                    {"role": "customer", "text": "А точно встанет в мою фару?"},
                    {"role": "seller", "text": "По вашей конфигурации эта модель имеет подтвержденную совместимость. Но если у вас уже стояли другие линзы, лучше уточнить тип цоколя."}
                ],
                "successful_strategy": ["check_database", "provide_confirmation", "offer_verification"],
                "mistakes_to_avoid": ["guess_compatibility", "overpromise"],
                "tags": ["compatibility", "objection", "technical"],
                "quality_score": 0.99,
                "language": "ru"
            }
        ],
        
        "trust_objections": [
            {
                "id": "sales_000090",
                "scenario": "trust_objection",
                "customer_profile": {"type": "skeptical", "experience": "medium"},
                "sales_stage": "objection",
                "intent": "trust_doubt",
                "emotion": "skeptical",
                "objection": "trust_issue",
                "goal": "build_trust",
                "dialogue": [
                    {"role": "customer", "text": "А вдруг через полгода сгорит?"},
                    {"role": "seller", "text": "Такой риск полностью исключить нельзя ни у одной электронной детали. Поэтому здесь важны гарантия, условия эксплуатации и правильная установка. Могу рассказать, какая гарантия идет на эту модель."}
                ],
                "successful_strategy": ["acknowledge_risk", "emphasize_warranty", "mention_conditions"],
                "mistakes_to_avoid": ["false_assurance", "ignore_risk"],
                "tags": ["trust", "objection", "warranty"],
                "quality_score": 0.96,
                "language": "ru"
            }
        ],
        
        "delivery": [
            {
                "id": "sales_000100",
                "scenario": "delivery",
                "customer_profile": {"type": "newbie", "experience": "none"},
                "sales_stage": "qualification",
                "intent": "delivery_inquiry",
                "emotion": "neutral",
                "objection": None,
                "goal": "provide_delivery_info",
                "dialogue": [
                    {"role": "customer", "text": "Сколько времени доставка?"},
                    {"role": "seller", "text": "Доставка по Москве — 1-2 дня, в другие регионы — 3-5 дней. Точные сроки зависят от удаленности и выбранной службы доставки. Доставка по России и СНГ бесплатная для розничных клиентов."}
                ],
                "successful_strategy": ["provide_clear_info", "mention_free_delivery", "ask_location"],
                "mistakes_to_avoid": ["vague_answer", "ignore_location"],
                "tags": ["delivery", "shipping", "timing"],
                "quality_score": 0.98,
                "language": "ru"
            }
        ],
        
        "warranty": [
            {
                "id": "sales_000110",
                "scenario": "warranty",
                "customer_profile": {"type": "newbie", "experience": "none"},
                "sales_stage": "qualification",
                "intent": "warranty_inquiry",
                "emotion": "neutral",
                "objection": None,
                "goal": "explain_warranty_terms",
                "dialogue": [
                    {"role": "customer", "text": "Какая гарантия?"},
                    {"role": "seller", "text": "На все наши линзы стандартная гарантия 24 месяца с даты покупки. Она покрывает дефекты производства и преждевременный выход из строя. При необходимости — бесплатная замена."}
                ],
                "successful_strategy": ["provide_clear_info", "explain_coverage", "mention_replacement"],
                "mistakes_to_avoid": ["vague_answer", "overpromise"],
                "tags": ["warranty", "guarantee", "coverage"],
                "quality_score": 0.99,
                "language": "ru"
            }
        ],
        
        "installation": [
            {
                "id": "sales_000120",
                "scenario": "installation",
                "customer_profile": {"type": "diy", "experience": "medium"},
                "sales_stage": "qualification",
                "intent": "installation_inquiry",
                "emotion": "neutral",
                "objection": None,
                "goal": "provide_installation_info",
                "dialogue": [
                    {"role": "customer", "text": "Я сам буду ставить. Что нужно?"},
                    {"role": "seller", "text": "Тогда могу обратить внимание на несколько моментов по установке. Подскажите, уже разбирали эту фару раньше или это будет первая переделка?"}
                ],
                "successful_strategy": ["identify_experience", "offer_help", "ask_previous_experience"],
                "mistakes_to_avoid": ["assume_experience", "ignore_safety"],
                "tags": ["installation", "diy", "safety"],
                "quality_score": 0.95,
                "language": "ru"
            }
        ],
        
        "upsell": [
            {
                "id": "sales_000130",
                "scenario": "upsell",
                "customer_profile": {"type": "technical", "experience": "high"},
                "sales_stage": "recommendation",
                "intent": "upsell_opportunity",
                "emotion": "interested",
                "objection": None,
                "goal": "offer_premium_option",
                "dialogue": [
                    {"role": "customer", "text": "Мне нравится эта модель."},
                    {"role": "seller", "text": "Отличный выбор! К этой линзе можно добавить комплект креплений, который упростит установку. Если хотите, могу показать, что именно туда входит."}
                ],
                "successful_strategy": ["acknowledge_choice", "offer_complementary", "explain_benefits"],
                "mistakes_to_avoid": ["push_unnecessary", "overwhelm"],
                "tags": ["upsell", "complementary", "accessories"],
                "quality_score": 0.96,
                "language": "ru"
            }
        ],
        
        "cross_sell": [
            {
                "id": "sales_000140",
                "scenario": "cross_sell",
                "customer_profile": {"type": "technical", "experience": "high"},
                "sales_stage": "recommendation",
                "intent": "cross_sell_opportunity",
                "emotion": "interested",
                "objection": None,
                "goal": "offer_related_products",
                "dialogue": [
                    {"role": "customer", "text": "Беру эти линзы."},
                    {"role": "seller", "text": "Отлично! Если будете переделывать фары полностью, возможно, пригодится также комплект креплений. Могу проверить, нужен ли он именно для вашей конфигурации."}
                ],
                "successful_strategy": ["acknowledge_purchase", "offer_related", "check_compatibility"],
                "mistakes_to_avoid": ["push_unnecessary", "overwhelm"],
                "tags": ["cross_sell", "related", "accessories"],
                "quality_score": 0.95,
                "language": "ru"
            }
        ],
        
        "closing": [
            {
                "id": "sales_000150",
                "scenario": "closing",
                "customer_profile": {"type": "ready_to_buy", "experience": "medium"},
                "sales_stage": "closing",
                "intent": "purchase_intent",
                "emotion": "ready_to_buy",
                "objection": None,
                "goal": "complete_sale",
                "dialogue": [
                    {"role": "customer", "text": "Сколько стоит?"},
                    {"role": "seller", "text": "Эта модель стоит 18900₽ за комплект. Если хотите оформить заказ, могу зафиксировать модель и количество."}
                ],
                "successful_strategy": ["state_price", "offer_order", "confirm_details"],
                "mistakes_to_avoid": ["pressure", "rush_customer"],
                "tags": ["closing", "price", "order"],
                "quality_score": 0.98,
                "language": "ru"
            }
        ],
        
        "hesitation": [
            {
                "id": "sales_000160",
                "scenario": "hesitation",
                "customer_profile": {"type": "indecisive", "experience": "medium"},
                "sales_stage": "hesitation",
                "intent": "hesitation",
                "emotion": "uncertain",
                "objection": None,
                "goal": "reduce_hesitation",
                "dialogue": [
                    {"role": "customer", "text": "Я подумаю."},
                    {"role": "seller", "text": "Конечно. Если хотите, могу коротко зафиксировать два подходящих варианта с разницей между ними, чтобы потом было проще сравнить."}
                ],
                "successful_strategy": ["respect_decision", "offer_help", "provide_comparison"],
                "mistakes_to_avoid": ["pressure", "rush_customer", "ignore_hesitation"],
                "tags": ["hesitation", "comparison", "decision"],
                "quality_score": 0.97,
                "language": "ru"
            }
        ],
        
        "order": [
            {
                "id": "sales_000170",
                "scenario": "order",
                "customer_profile": {"type": "ready_to_buy", "experience": "medium"},
                "sales_stage": "order",
                "intent": "order_request",
                "emotion": "ready_to_buy",
                "objection": None,
                "goal": "process_order",
                "dialogue": [
                    {"role": "customer", "text": "Хочу оформить заказ."},
                    {"role": "seller", "text": "Отлично! Для оформления заказа мне нужны: ваше ФИО, телефон для связи и адрес доставки. Также уточните, как будете оплачивать."}
                ],
                "successful_strategy": ["confirm_intent", "collect_info", "explain_process"],
                "mistakes_to_avoid": ["complicate_process", "ask_unnecessary_info"],
                "tags": ["order", "checkout", "payment"],
                "quality_score": 0.98,
                "language": "ru"
            }
        ],
        
        "returning_customer": [
            {
                "id": "sales_000180",
                "scenario": "returning_customer",
                "customer_profile": {"type": "repeat_customer", "experience": "high"},
                "sales_stage": "greeting",
                "intent": "returning_customer",
                "emotion": "neutral",
                "objection": None,
                "goal": "recognize_and_welcome",
                "dialogue": [
                    {"role": "customer", "text": "Вы мне вчера советовали OrionLight SATURN."},
                    {"role": "seller", "text": "Да, помню, мы смотрели вариант OrionLight SATURN для вашего автомобиля. Хотите продолжить с ним или появились вопросы?"}
                ],
                "successful_strategy": ["recognize_customer", "reference_previous", "offer_continuation"],
                "mistakes_to_avoid": ["ignore_history", "ask_repeated_questions"],
                "tags": ["returning", "recognition", "continuation"],
                "quality_score": 0.99,
                "language": "ru"
            }
        ],
        
        "professional_buyer": [
            {
                "id": "sales_000190",
                "scenario": "professional_buyer",
                "customer_profile": {"type": "professional", "experience": "high"},
                "sales_stage": "qualification",
                "intent": "professional_inquiry",
                "emotion": "neutral",
                "objection": None,
                "goal": "provide_quick_info",
                "dialogue": [
                    {"role": "customer", "text": "Нужны линзы 3 дюйма, 10 комплектов."},
                    {"role": "seller", "text": "Понял. OrionLight SATURN 3 дюйма, 10 комплектов. Цена 8900₽ за комплект, итого 89000₽. В наличии 15 комплектов. Доставка до вашего города 2-3 дня. Нужна накладная?"}
                ],
                "successful_strategy": ["be_concise", "provide_essentials", "ask_necessary_details"],
                "mistakes_to_avoid": ["too_verbose", "ask_unnecessary_questions"],
                "tags": ["professional", "wholesale", "quick"],
                "quality_score": 0.98,
                "language": "ru"
            }
        ],
        
        "handoff": [
            {
                "id": "sales_000200",
                "scenario": "handoff",
                "customer_profile": {"type": "technical", "experience": "high"},
                "sales_stage": "objection",
                "intent": "complex_question",
                "emotion": "neutral",
                "objection": "complex_issue",
                "goal": "transfer_to_human",
                "dialogue": [
                    {"role": "customer", "text": "Можно ли установить на мою машину с нестандартной оптикой?"},
                    {"role": "seller", "text": "Здесь не хочу вводить вас в заблуждение. Лучше передам вопрос специалисту, который сможет проверить конкретно вашу фару."}
                ],
                "successful_strategy": ["acknowledge_limitation", "offer_handoff", "explain_reason"],
                "mistakes_to_avoid": ["guess", "provide_incorrect_info"],
                "tags": ["handoff", "complex", "specialist"],
                "quality_score": 0.99,
                "language": "ru"
            }
        ],
        
        "need_discovery": [
            {
                "id": "sales_000010",
                "scenario": "need_discovery",
                "customer_profile": {"type": "newbie", "experience": "none"},
                "sales_stage": "discovery",
                "intent": "need_discovery",
                "emotion": "neutral",
                "objection": None,
                "goal": "discover_need",
                "dialogue": [
                    {"role": "customer", "text": "Хочу поставить линзы, но не знаю какие."},
                    {"role": "seller", "text": "Давайте подберём. Напишите марку, модель и год автомобиля. И ещё подскажите, фары сейчас штатные или уже кто-то переделывал?"}
                ],
                "successful_strategy": ["ask_vehicle", "ask_year", "ask_current_configuration", "avoid_product_dump"],
                "mistakes_to_avoid": ["product_dump", "overwhelm_customer", "assume_vehicle"],
                "tags": ["need_discovery", "vehicle_qualification"],
                "quality_score": 0.95,
                "language": "ru"
            }
        ],
        
        "price_objections": [
            {
                "id": "sales_000051",
                "scenario": "price_objection",
                "customer_profile": {"type": "price_sensitive", "experience": "medium"},
                "sales_stage": "objection",
                "intent": "price_comparison",
                "emotion": "skeptical",
                "objection": "too_expensive",
                "goal": "discover_budget",
                "dialogue": [
                    {"role": "customer", "text": "Дорого."},
                    {"role": "seller", "text": "Понимаю. Если ориентируетесь на определённый бюджет, скажите примерно сумму — посмотрю, есть ли вариант ближе к ней."}
                ],
                "successful_strategy": ["acknowledge_objection", "discover_budget", "offer_alternative"],
                "mistakes_to_avoid": ["pressure", "defend_price", "fake_discount", "claim_cheapest"],
                "tags": ["price", "budget", "alternative"],
                "quality_score": 0.97,
                "language": "ru"
            }
        ]
    }
    
    return dialogues


def main():
    """Generate all Sales RAG dialogues."""
    print("🚀 Generating complete Sales RAG Dataset...")
    
    # Generate all dialogues
    all_dialogues = generate_all_dialogues()
    
    # Define output directory
    output_dir = Path("ai_seller/rag/seller_dialogues")
    
    # Save each category
    total_count = 0
    for category, dialogues in all_dialogues.items():
        save_dialogues(dialogues, f"{category}.jsonl", output_dir)
        total_count += len(dialogues)
    
    print(f"\n✅ All Sales RAG dialogues generated!")
    print(f"📊 Total: {total_count} dialogues across {len(all_dialogues)} categories")
    print(f"\n📁 Files created in: {output_dir}")


if __name__ == "__main__":
    main()
