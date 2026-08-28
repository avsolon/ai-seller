"""Script to import and convert knowledge base data to required format."""

import json
import os
from pathlib import Path
from typing import Any, Dict, List
import unicodedata


def slugify(text: str) -> str:
    """Convert text to slug format."""
    # Normalize unicode characters
    text = unicodedata.normalize('NFKD', text)
    
    # Remove special characters
    text = ''.join(c for c in text if not unicodedata.category(c).startswith('P'))
    
    # Replace spaces and special chars
    text = text.replace(' ', '_').replace('/', '_').replace('\\', '_')
    
    # Remove multiple underscores
    while '__' in text:
        text = text.replace('__', '_')
    
    # Remove leading/trailing underscores
    text = text.strip('_')
    
    return text.lower()


def convert_company_info(company_data: Dict[str, Any], output_dir: Path) -> None:
    """Convert company info to markdown and JSON formats."""
    company = company_data.get("company_info", {})
    
    # Create company directory
    company_dir = output_dir / "company"
    company_dir.mkdir(parents=True, exist_ok=True)
    
    # Markdown format
    contacts = company.get('contacts', {})
    working_hours = company.get('working_hours', {})
    sales_dept = working_hours.get('sales_department', {})
    service_center = working_hours.get('service_center', {})
    address = company.get('address', {})
    
    markdown_content = f"""# {company.get('name', 'Company Name')}

## Legal Information
- **Legal Name:** {company.get('legal_name', 'N/A')}
- **INN:** {company.get('inn', 'N/A')}
- **OGRNIP:** {company.get('ogrnip', 'N/A')}
- **Legal Address:** {company.get('legal_address', 'N/A')}
- **Location:** {company.get('location', 'N/A')}

## Contact Information
- **Phone:** {contacts.get('phone', 'N/A')}
- **Email:** {contacts.get('email', 'N/A')}
- **Telegram:** {contacts.get('telegram', 'N/A')}
- **WhatsApp:** {contacts.get('whatsapp', 'N/A')}
- **YouTube:** {contacts.get('youtube', 'N/A')}
- **VK:** {contacts.get('vk', 'N/A')}

## Working Hours

### Sales Department
- **Days:** {sales_dept.get('days', 'N/A')}
- **Time:** {sales_dept.get('time', 'N/A')}
- **Weekend:** {sales_dept.get('weekend', 'N/A')}

### Service Center
- **Status:** {service_center.get('status', 'N/A')}

## Address
- **Office:** {address.get('office', 'N/A')}

## Delivery
{company.get('delivery', 'N/A')}

## About Us
Fara Line is a leading provider of high-quality LED and xenon lighting solutions for automobiles. 
We specialize in Bi-LED modules, xenon lamps, and automotive lighting accessories.
"""
    
    # Save markdown
    with open(company_dir / "about.md", "w", encoding="utf-8") as f:
        f.write(markdown_content)
    
    # Save JSON
    with open(company_dir / "contacts.json", "w", encoding="utf-8") as f:
        json.dump(company_data.get("company_info", {}), f, ensure_ascii=False, indent=2)
    
    print(f"✅ Company info saved to {company_dir}")


def convert_product_to_markdown(product: Dict[str, Any]) -> str:
    """Convert a single product to markdown format."""
    characteristics = product.get("characteristics", {})
    
    markdown = f"""# {product.get('name', 'Unknown')}

**Category:** {product.get('category', 'Unknown')}
**ID:** {product.get('id', 'N/A')}
**Price:** {product.get('price', 0)} RUB
**Availability:** {product.get('availability', 'Unknown')}
**URL:** {product.get('url', '#')}

## Description
{product.get('description', 'No description available')}

## Technical Specifications

"""
    
    # Add characteristics as a table
    if characteristics:
        markdown += "| Characteristic | Value |\n"
        markdown += "|----------------|-------|\n"
        for key, value in characteristics.items():
            markdown += f"| {key} | {value} |\n"
    
    markdown += "\n"
    return markdown


def convert_products_to_markdown(products_data: List[Dict[str, Any]], output_dir: Path) -> None:
    """Convert products list to markdown files."""
    products_dir = output_dir / "products"
    products_dir.mkdir(parents=True, exist_ok=True)
    
    # Group products by category
    categories = {}
    for product in products_data:
        category = product.get("category", "Other")
        if category not in categories:
            categories[category] = []
        categories[category].append(product)
    
    # Create directory for each category
    for category, products in categories.items():
        # Create safe category name
        safe_category = slugify(category)
        subcategory_dir = products_dir / safe_category
        subcategory_dir.mkdir(parents=True, exist_ok=True)
        
        # Create index file for subcategory
        index_content = f"""# {category}

This category contains {len(products)} products.

## Product List

"""
        
        for product in products:
            # Create safe filename
            safe_name = slugify(product.get("name", "unknown"))[:50]
            filename = f"{safe_name}.md"
            filepath = subcategory_dir / filename
            
            # Save product markdown
            product_md = convert_product_to_markdown(product)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(product_md)
            
            # Add to index
            index_content += f"- [{product.get('name', 'Unknown')}]({filename})\n"
        
        # Save index
        with open(subcategory_dir / "README.md", "w", encoding="utf-8") as f:
            f.write(index_content)
        
        print(f"✅ Created {len(products)} products in {subcategory_dir}")


def convert_to_jsonl(products_data: List[Dict[str, Any]], output_dir: Path, filename: str) -> None:
    """Convert products to JSONL format for RAG."""
    with open(output_dir / filename, "w", encoding="utf-8") as f:
        for product in products_data:
            # Create RAG-friendly format
            rag_entry = {
                "id": product.get("id", ""),
                "name": product.get("name", ""),
                "category": product.get("category", ""),
                "price": product.get("price", 0),
                "availability": product.get("availability", ""),
                "description": product.get("description", ""),
                "characteristics": product.get("characteristics", {}),
                "url": product.get("url", ""),
                "source": "product_database",
                "type": "product",
                "language": "ru",
                "version": "1.0"
            }
            f.write(json.dumps(rag_entry, ensure_ascii=False) + "\n")
    
    print(f"✅ Created JSONL file: {output_dir / filename}")


def create_faq_from_products(products_data: List[Dict[str, Any]], output_dir: Path) -> None:
    """Create FAQ entries from product data."""
    faq_dir = output_dir / "faq"
    faq_dir.mkdir(parents=True, exist_ok=True)
    
    faq_entries = []
    
    # Common questions about LED lenses
    led_lenses = [p for p in products_data if p.get("category") == "Светодиодные линзы"]
    if led_lenses:
        faq_entries.append({
            "id": "faq_led_001",
            "question": "Какие светодиодные линзы подойдут для моего автомобиля?",
            "answer": "Подбор зависит от модели автомобиля, типа фар и ваших предпочтений. Мы предлагаем линзы размером 1.5, 2.5 и 3 дюйма. Для точного подбора уточните марку, модель и год вашего автомобиля.",
            "category": "product_selection",
            "tags": ["совместимость", "подбор", "автомобиль"],
            "priority": 1
        })
        
        faq_entries.append({
            "id": "faq_led_002",
            "question": "Чем отличаются линзы с разной цветовой температурой?",
            "answer": "Цветовая температура измеряется в Кельвинах (K). 4300K - теплый белый свет, 5000K - нейтральный белый, 5500K-6000K - холодный белый с голубоватым оттенком. Для городского использования часто выбирают 5000-5500K.",
            "category": "technical",
            "tags": ["цветовая температура", "кельвины", "свет"],
            "priority": 2
        })
        
        faq_entries.append({
            "id": "faq_led_003",
            "question": "Сколько служат светодиодные линзы?",
            "answer": "Средний срок службы качественных светодиодных линз составляет 30000-50000 часов, что эквивалентно 10-15 годам при стандартной эксплуатации.",
            "category": "technical",
            "tags": ["срок службы", "долговечность"],
            "priority": 3
        })
    
    # Questions about xenon lamps
    xenon_lamps = [p for p in products_data if p.get("category") == "Ксеноновые лампы"]
    if xenon_lamps:
        faq_entries.append({
            "id": "faq_xenon_001",
            "question": "В чем разница между ксеноновыми лампами D1S, D2S, D3S, D4S?",
            "answer": "Основное отличие в цоколе и конструкции. D1S и D3S имеют встроенный блок розжига, D2S и D4S требуют внешнего блока. D3S и D4S - более современные версии с улучшенными характеристиками.",
            "category": "technical",
            "tags": ["ксенон", "цоколь", "разница"],
            "priority": 2
        })
    
    # Save FAQ as JSONL
    with open(faq_dir / "products.jsonl", "w", encoding="utf-8") as f:
        for entry in faq_entries:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    print(f"✅ Created FAQ with {len(faq_entries)} entries")


def create_delivery_info(company_data: Dict[str, Any], output_dir: Path) -> None:
    """Create delivery information."""
    delivery_dir = output_dir / "delivery"
    delivery_dir.mkdir(parents=True, exist_ok=True)
    
    company_info = company_data.get('company_info', {})
    delivery_text = company_info.get('delivery', 'N/A')
    
    delivery_info = f"""# Delivery Information

{delivery_text}

## Delivery Options
- **Free delivery** across Russia and CIS for retail customers
- **Courier service** available in major cities
- **Pickup** from our office in Novosibirsk

## Delivery Times
- **Moscow, St. Petersburg:** 1-2 business days
- **Other major cities:** 2-3 business days  
- **Regional areas:** 3-7 business days

## International Delivery
We ship to CIS countries with standard delivery times of 7-14 business days.
"""
    
    with open(delivery_dir / "terms.md", "w", encoding="utf-8") as f:
        f.write(delivery_info)
    
    print(f"✅ Delivery info saved to {delivery_dir / 'terms.md'}")


def create_warranty_info(output_dir: Path) -> None:
    """Create warranty information."""
    warranty_dir = output_dir / "warranty"
    warranty_dir.mkdir(parents=True, exist_ok=True)
    
    warranty_info = """# Warranty Terms

## Standard Warranty
- **Duration:** 24 months from date of purchase
- **Coverage:** Manufacturing defects, premature failure
- **What is covered:** All LED and xenon products

## Extended Warranty
- **Available for:** Premium product lines
- **Duration:** Up to 36 months
- **Conditions:** Proper installation and usage

## Warranty Claim Process
1. Present your receipt or invoice
2. Describe the issue
3. Send the product for inspection (shipping paid by seller)
4. Receive replacement or repair

## What is NOT Covered
- Mechanical damage
- Improper installation
- Usage in non-standard conditions
- Modifications to the product

## Important Notes
- Warranty is valid only for the original purchaser
- Proof of purchase is required
- Products must be used according to manufacturer specifications
"""
    
    with open(warranty_dir / "terms.md", "w", encoding="utf-8") as f:
        f.write(warranty_info)
    
    print(f"✅ Warranty info saved to {warranty_dir / 'terms.md'}")


def main():
    """Main conversion function."""
    print("🚀 Starting knowledge base conversion...")
    
    # Define output directory
    output_dir = Path("ai_seller/rag/knowledge")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    try:
        # Load knowledge base data
        with open("knowledge_base.json", "r", encoding="utf-8") as f:
            knowledge_data = json.load(f)
        
        # Load LED lenses data
        with open("svetodiodnye_linzy.json", "r", encoding="utf-8") as f:
            led_lenses_data = json.load(f)
        
        # Convert company info
        print("\n📋 Converting company information...")
        convert_company_info(knowledge_data, output_dir)
        
        # Convert products from knowledge base
        print("\n📦 Converting products from knowledge base...")
        kb_products = knowledge_data.get("products", [])
        convert_products_to_markdown(kb_products, output_dir)
        
        # Convert LED lenses
        print("\n💡 Converting LED lenses...")
        convert_products_to_markdown(led_lenses_data, output_dir)
        
        # Create combined product JSONL for RAG
        print("\n🔍 Creating RAG JSONL files...")
        all_products = kb_products + led_lenses_data
        convert_to_jsonl(all_products, output_dir, "products.jsonl")
        
        # Create FAQ
        print("\n❓ Creating FAQ...")
        create_faq_from_products(led_lenses_data, output_dir)
        
        # Create delivery info
        print("\n🚚 Creating delivery information...")
        create_delivery_info(knowledge_data, output_dir)
        
        # Create warranty info
        print("\n🛡️ Creating warranty information...")
        create_warranty_info(output_dir)
        
        print("\n✅ All knowledge base data converted successfully!")
        print(f"\n📁 Files created in: {output_dir}")
        
    except FileNotFoundError as e:
        print(f"❌ Error: File not found - {e}")
        print("\nPlease make sure knowledge_base.json and svetodiodnye_linzy.json exist in the current directory.")
    except Exception as e:
        print(f"❌ Error: {e}")


if __name__ == "__main__":
    main()
