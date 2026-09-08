#!/usr/bin/env python3
"""
Full catalog scraper for faraline.ru - Optimized version
Collects ALL products from all 14 pages of the catalog (https://faraline.ru/shop-2/)
with complete characteristics parsing from names and descriptions.
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import List, Dict, Optional
from urllib.parse import urlparse

BASE_URL = "https://faraline.ru"
CATALOG_URL = f"{BASE_URL}/shop-2/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def get_product_urls_from_page(page_url: str) -> List[str]:
    """Extract all product URLs from a catalog page."""
    try:
        print(f"  Fetching page: {page_url}")
        response = requests.get(page_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        product_urls = []
        seen = set()
        
        # Find all links
        all_links = soup.find_all('a', href=True)
        for link in all_links:
            href = link['href']
            if href.startswith(f"{BASE_URL}/product/") and href not in seen:
                seen.add(href)
                product_urls.append(href)
        
        print(f"  Found {len(product_urls)} unique product URLs")
        return product_urls
    except Exception as e:
        print(f"  ✗ Error getting product URLs from {page_url}: {e}")
        return []


def extract_category_from_url(url: str) -> str:
    """Extract category from product URL path."""
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    
    # Look for category in path
    for part in path_parts:
        if part != 'product' and part != 'shop-2' and part != 'page':
            return part.replace('-2', '').replace('-', ' ').title()
    return "Unknown"


def extract_category_from_breadcrumbs(soup: BeautifulSoup) -> str:
    """Extract category from breadcrumbs."""
    breadcrumbs = soup.find('nav', class_=lambda x: x and 'breadcrumb' in x.lower())
    if breadcrumbs:
        links = breadcrumbs.find_all('a')
        if len(links) >= 2:
            # Get all breadcrumb links
            categories = [link.get_text(strip=True) for link in links]
            # Filter out home and shop pages
            categories = [c for c in categories if c.lower() not in ['главная', 'магазин', 'shop', 'каталог']]
            if categories:
                return categories[-1]  # Last category
    return "Unknown"


def parse_characteristics_from_text(text: str) -> Dict:
    """Parse characteristics from product name and description."""
    characteristics = {
        "тип": "",
        "модель": "",
        "размер": "",
        "напряжение": "",
        "цветовая_температура": "",
        "мощность": "",
        "комплектация": "",
        "особенности": ""
    }
    
    if not text:
        return characteristics
    
    # Normalize text
    text_lower = text.lower()
    
    # Type detection
    type_patterns = [
        (r'светодиодн[ыы]?е?\s+линз[ыы]', 'Светодиодные линзы'),
        (r'светодиодн[ыы]?е?\s+ламп[ыы]', 'Светодиодные лампы'),
        (r'ксенонов[ыы]?е?\s+ламп[ыы]', 'Ксеноновые лампы'),
        (r'би-лед\s+модул[ия]', 'Би-лед модули'),
        (r'светодиодн[ыы]?е?\s+матричн[ыы]?е?\s+би-лед\s+модул[ия]', 'Светодиодные матричные би-лед модули'),
        (r'герметик', 'Герметик'),
        (r'переходн[ая]?\s+рамк[аи]', 'Переходные рамки'),
        (r'блок\s+розжиг[аи]', 'Блок розжига'),
        (r'провод[аи]', 'Провода'),
        (r'разъем[ыи]', 'Разъемы'),
        (r'реле', 'Реле'),
    ]
    
    for pattern, type_name in type_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            characteristics["тип"] = type_name
            break
    
    # Size (1.5", 2.5", 3", etc.)
    size_match = re.search(r'(\d+\.?\d*)(?:"|″|&#8243;|дюйм[аов]?)', text, re.IGNORECASE)
    if size_match:
        characteristics["размер"] = size_match.group(1) + '"'
    
    # Voltage (12V, 24V, etc.)
    voltage_match = re.search(r'(\d+)\s*V|(\d+)\s*вольт[аов]?|(\d+)V', text, re.IGNORECASE)
    if voltage_match:
        voltage = voltage_match.group(1) or voltage_match.group(2) or voltage_match.group(3)
        characteristics["напряжение"] = f"{voltage}V"
    
    # Color temperature (5000K, 5500K, 6000K, etc.)
    temp_match = re.search(r'(\d+)\s*K|(\d+)\s*кельвин[аов]?|(\d+)K', text, re.IGNORECASE)
    if temp_match:
        temp = temp_match.group(1) or temp_match.group(2) or temp_match.group(3)
        characteristics["цветовая_температура"] = f"{temp}K"
    
    # Power (50W, 60W, etc.)
    power_match = re.search(r'(\d+)\s*W|(\d+)\s*ватт[аы]?|(\d+)W', text, re.IGNORECASE)
    if power_match:
        power = power_match.group(1) or power_match.group(2) or power_match.group(3)
        characteristics["мощность"] = f"{power}W"
    
    # Model - try to extract from text
    model_match = re.search(r'(ORIONLIGHT[\s\w()\-]+)|(PL\d+-\d+)|(ALIEN[\s\w]*)|([A-Z]{2,}\d+[\w\-]*)', text, re.IGNORECASE)
    if model_match:
        model = model_match.group(1) or model_match.group(2) or model_match.group(3) or model_match.group(4)
        if model:
            characteristics["модель"] = model.strip()
    
    # Kit/complectation
    kit_patterns = [
        r'Цена\s+за\s+комплект\([^)]+\)',
        r'комплект\s+\([^)]+\)',
        r'в\s+комплекте\s+[^.,;]+',
        r'комплект\s+из\s+\d+\s+шт',
    ]
    for pattern in kit_patterns:
        kit_match = re.search(pattern, text, re.IGNORECASE)
        if kit_match:
            characteristics["комплектация"] = kit_match.group().strip()
            break
    
    # Features
    features = []
    feature_patterns = [
        (r'со\s+встроенной\s+обманкой', 'со встроенной обманкой'),
        (r'с\s+шагренью', 'с шагренью'),
        (r'без\s+четкой\s+СТГ', 'без четкой СТГ'),
        (r'левый\s+руль', 'левый руль'),
        (r'прям[аяя]', 'прямая'),
        (r'\(3\s+чип[аа]\s+и\s+3\s+отражател[яе]\)', '3 чипа и 3 отражателя'),
        (r'\(gen\s+1\)', 'GEN 1'),
        (r'\(gen2\)', 'GEN2'),
        (r'\(gen\s+2\)', 'GEN 2'),
    ]
    
    for pattern, feature_text in feature_patterns:
        if re.search(pattern, text_lower, re.IGNORECASE):
            features.append(feature_text)
    
    if features:
        characteristics["особенности"] = ', '.join(features)
    
    return characteristics


def merge_characteristics(from_name: Dict, from_desc: Dict, from_table: Dict) -> Dict:
    """Merge characteristics from different sources, prioritizing non-empty values."""
    merged = {
        "тип": from_name.get("тип", "") or from_desc.get("тип", "") or from_table.get("Тип", "") or from_table.get("тип", ""),
        "модель": from_name.get("модель", "") or from_desc.get("модель", "") or from_table.get("Модель", "") or from_table.get("модель", ""),
        "размер": from_name.get("размер", "") or from_desc.get("размер", "") or from_table.get("Размер", "") or from_table.get("размер", ""),
        "напряжение": from_name.get("напряжение", "") or from_desc.get("напряжение", "") or from_table.get("Напряжение", "") or from_table.get("напряжение", ""),
        "цветовая_температура": from_name.get("цветовая_температура", "") or from_desc.get("цветовая_температура", "") or from_table.get("Цветовая температура", "") or from_table.get("цветовая температура", ""),
        "мощность": from_name.get("мощность", "") or from_desc.get("мощность", "") or from_table.get("Мощность", "") or from_table.get("мощность", ""),
        "комплектация": from_name.get("комплектация", "") or from_desc.get("комплектация", "") or from_table.get("Комплектация", "") or from_table.get("комплектация", ""),
        "особенности": from_name.get("особенности", "") or from_desc.get("особенности", "") or from_table.get("Особенности", "") or from_table.get("особенности", ""),
    }
    return merged


def scrape_product_page(product_url: str) -> Optional[Dict]:
    """Scrape data from a single product page."""
    try:
        print(f"    Scraping: {product_url}")
        response = requests.get(product_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract product name
        name_tag = soup.find('h1')
        name = name_tag.get_text(strip=True) if name_tag else 'N/A'
        
        # Initialize product data
        product_data = {
            'id': 'N/A',
            'name': name,
            'description': '',
            'price': 0,
            'availability': 'Нет в наличии',
            'category': '',
            'characteristics': {},
            'url': product_url
        }
        
        # Extract product ID and price from JavaScript
        scripts = soup.find_all('script')
        for script in scripts:
            if 'var item' in str(script):
                text = script.string
                if text:
                    match = re.search(r'var item = (\{.*?\});', text, re.DOTALL)
                    if match:
                        try:
                            item_json = match.group(1)
                            item_data = json.loads(item_json)
                            
                            if 'product_id' in item_data:
                                product_data['id'] = str(item_data['product_id'])
                            if 'price' in item_data:
                                price_str = str(item_data['price'])
                                # Clean price string
                                price_clean = re.sub(r'[^\d.]', '', price_str)
                                try:
                                    product_data['price'] = int(float(price_clean)) if price_clean else 0
                                except:
                                    product_data['price'] = 0
                        except Exception as e:
                            print(f"    Warning: Error parsing item data: {e}")
                break
        
        # Extract availability
        availability_div = soup.find('div', class_='product-stock')
        if availability_div:
            availability_text = availability_div.get_text(strip=True)
            if 'в наличии' in availability_text.lower():
                product_data['availability'] = 'В наличии'
            else:
                product_data['availability'] = 'Нет в наличии'
        
        # Extract short description
        short_desc_div = soup.find('div', class_='woocommerce-product-details__short-description')
        if short_desc_div:
            product_data['description'] = short_desc_div.get_text(strip=True)
        
        # Parse characteristics from name first (needed for category detection)
        name_chars = parse_characteristics_from_text(name)
        
        # Extract category from product page - look for category links
        category = "Unknown"
        category_links = soup.find_all('a', href=lambda x: x and 'product-category' in x if x else False)
        if category_links:
            # Get all category texts
            categories = [link.get_text(strip=True) for link in category_links]
            # Try to find the most specific category that matches the product type
            product_type = name_chars.get('тип', '').lower()
            if product_type:
                # Find category that matches product type
                for cat in categories:
                    if product_type in cat.lower():
                        category = cat
                        break
            # If no match, use the first non-generic category
            if category == "Unknown":
                generic_categories = ['светодиодные линзы', 'обзор', 'магазин', 'shop']
                for cat in categories:
                    if cat.lower() not in generic_categories:
                        category = cat
                        break
        
        # Fallback to breadcrumbs
        if category == "Unknown":
            category = extract_category_from_breadcrumbs(soup)
        
        # Final fallback to URL
        if category == "Unknown":
            category = extract_category_from_url(product_url)
        
        product_data['category'] = category
        
        # Extract characteristics from attributes table
        table_chars = {}
        table = soup.find('table', class_='woocommerce-product-attributes__table')
        if table:
            rows = table.find_all('tr', class_='woocommerce-product-attributes-item')
            for row in rows:
                th = row.find('th', class_='woocommerce-product-attributes-item__label')
                td = row.find('td', class_='woocommerce-product-attributes-item__value')
                if th and td:
                    key = th.get_text(strip=True)
                    value = td.get_text(strip=True)
                    table_chars[key] = value
        
        # Parse characteristics from description
        desc_chars = parse_characteristics_from_text(product_data['description'])
        
        # Merge all characteristics
        merged_chars = merge_characteristics(name_chars, desc_chars, table_chars)
        product_data['characteristics'] = merged_chars
        
        # If type not detected, try from category
        if not product_data['characteristics'].get('тип'):
            product_data['characteristics']['тип'] = product_data['category']
        
        print(f"    ✓ Successfully scraped: {name}")
        return product_data
        
    except Exception as e:
        print(f"    ✗ Error scraping {product_url}: {e}")
        return None


def get_all_product_urls() -> List[str]:
    """Get all product URLs from all 14 pages of the catalog."""
    print("\n=== Step 1: Collecting all product URLs ===")
    all_urls = []
    seen = set()
    
    for page_num in range(1, 15):
        if page_num == 1:
            page_url = CATALOG_URL
        else:
            page_url = f"{CATALOG_URL}page/{page_num}/"
        
        print(f"\nProcessing page {page_num}/14...")
        product_urls = get_product_urls_from_page(page_url)
        
        for url in product_urls:
            if url not in seen:
                seen.add(url)
                all_urls.append(url)
        
        # Be polite with delay
        time.sleep(1)
    
    print(f"\n✓ Found {len(all_urls)} unique product URLs")
    return all_urls


def main():
    """Main function to scrape all products and save to JSON."""
    print("=" * 70)
    print("Starting to scrape ALL products from faraline.ru catalog")
    print("=" * 70)
    
    # Get all product URLs
    product_urls = get_all_product_urls()
    
    if not product_urls:
        print("\n✗ No product URLs found! Exiting...")
        return
    
    # Scrape each product
    print("\n=== Step 2: Scraping product details ===")
    products = []
    
    for i, url in enumerate(product_urls, 1):
        print(f"\nProcessing product {i}/{len(product_urls)}...")
        product_data = scrape_product_page(url)
        
        if product_data:
            products.append(product_data)
        
        # Be polite with delay
        time.sleep(1)
        
        # Save progress every 5 products
        if i % 5 == 0:
            print(f"\n  Saving progress after {i} products...")
            with open('full_knowledge_base_temp.json', 'w', encoding='utf-8') as f:
                json.dump(products, f, ensure_ascii=False, indent=2)
    
    # Save final results
    print("\n=== Step 3: Saving final results ===")
    output = {
        "products": products,
        "total_products": len(products),
        "total_found": len(product_urls),
        "source": "faraline.ru",
        "catalog_url": CATALOG_URL,
        "pages_scraped": 14,
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "structure": {
            "product": {
                "id": "string",
                "name": "string",
                "description": "string",
                "price": "integer",
                "availability": "string (В наличии/Нет в наличии)",
                "category": "string",
                "characteristics": {
                    "тип": "string",
                    "модель": "string",
                    "размер": "string",
                    "напряжение": "string",
                    "цветовая_температура": "string",
                    "мощность": "string",
                    "комплектация": "string",
                    "особенности": "string"
                },
                "url": "string"
            }
        }
    }
    
    with open('full_knowledge_base.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    # Clean up temp file
    import os
    if os.path.exists('full_knowledge_base_temp.json'):
        os.remove('full_knowledge_base_temp.json')
    
    print("\n" + "=" * 70)
    print(f"✓ Successfully completed!")
    print(f"  - Products successfully scraped: {len(products)}")
    print(f"  - Total product URLs found: {len(product_urls)}")
    print(f"  - Failed to scrape: {len(product_urls) - len(products)}")
    print(f"  - Data saved to: full_knowledge_base.json")
    print("=" * 70)


if __name__ == "__main__":
    main()
