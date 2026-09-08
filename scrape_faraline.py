#!/usr/bin/env python3
"""
Scraper for faraline.ru to collect product data from all 14 pages of the catalog.
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import List, Dict, Optional

BASE_URL = "https://faraline.ru"
CATALOG_URL = f"{BASE_URL}/shop-2/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_product_urls_from_page(page_url: str) -> List[str]:
    """Extract all product URLs from a catalog page."""
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        product_urls = []
        links = soup.find_all('a', href=True)
        
        for link in links:
            href = link['href']
            if href.startswith(f"{BASE_URL}/product/") and href not in product_urls:
                product_urls.append(href)
        
        return product_urls
    except Exception as e:
        print(f"Error getting product URLs from {page_url}: {e}")
        return []

def scrape_product_page(product_url: str) -> Optional[Dict]:
    """Scrape data from a single product page."""
    try:
        response = requests.get(product_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract product name
        name_tag = soup.find('h1')
        name = name_tag.get_text(strip=True) if name_tag else 'N/A'
        
        # Extract product data from JavaScript
        scripts = soup.find_all('script')
        product_data = {
            'id': 'N/A',
            'name': name,
            'description': 'N/A',
            'price': 'N/A',
            'availability': 'N/A',
            'category': 'N/A',
            'characteristics': {},
            'url': product_url
        }
        
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
                                product_data['price'] = str(item_data['price']).replace('&nbsp;', ' ').replace('₽', '').strip()
                            if 'categories' in item_data and item_data['categories']:
                                product_data['category'] = item_data['categories'][0]
                        except Exception as e:
                            print(f"Error parsing item data: {e}")
                break
        
        # Extract availability
        availability_div = soup.find('div', class_='product-stock')
        if availability_div:
            product_data['availability'] = availability_div.get_text(strip=True)
        
        # Extract short description
        short_desc_div = soup.find('div', class_='woocommerce-product-details__short-description')
        if short_desc_div:
            product_data['description'] = short_desc_div.get_text(strip=True)
        
        # Extract characteristics from product attributes table
        table = soup.find('table', class_='woocommerce-product-attributes__table')
        if table:
            characteristics = {}
            rows = table.find_all('tr', class_='woocommerce-product-attributes-item')
            for row in rows:
                th = row.find('th', class_='woocommerce-product-attributes-item__label')
                td = row.find('td', class_='woocommerce-product-attributes-item__value')
                if th and td:
                    key = th.get_text(strip=True)
                    value = td.get_text(strip=True)
                    characteristics[key] = value
            product_data['characteristics'] = characteristics
        
        return product_data
        
    except Exception as e:
        print(f"Error scraping {product_url}: {e}")
        return None

def get_all_product_urls() -> List[str]:
    """Get all product URLs from all 14 pages of the catalog."""
    all_urls = []
    
    for page_num in range(1, 15):
        if page_num == 1:
            page_url = CATALOG_URL
        else:
            page_url = f"{CATALOG_URL}page/{page_num}/"
        
        print(f"Processing page {page_num}: {page_url}")
        product_urls = get_product_urls_from_page(page_url)
        all_urls.extend(product_urls)
        
        # Be polite with delay
        time.sleep(2)
    
    # Remove duplicates while preserving order
    unique_urls = []
    seen = set()
    for url in all_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    return unique_urls

def main():
    """Main function to scrape all products and save to JSON."""
    print("Starting to scrape faraline.ru...")
    
    # Get all product URLs
    print("\n1. Collecting all product URLs...")
    product_urls = get_all_product_urls()
    print(f"Found {len(product_urls)} unique product URLs")
    
    # Scrape each product
    print("\n2. Scraping product details...")
    products = []
    
    for i, url in enumerate(product_urls, 1):
        print(f"Scraping product {i}/{len(product_urls)}: {url}")
        product_data = scrape_product_page(url)
        
        if product_data:
            products.append(product_data)
            print(f"  ✓ Successfully scraped: {product_data.get('name', 'Unknown')}")
        else:
            print(f"  ✗ Failed to scrape: {url}")
        
        # Be polite with delay
        time.sleep(1)
    
    # Save to JSON file
    print("\n3. Saving results...")
    output = {
        "products": products,
        "total_products": len(products),
        "source": "faraline.ru",
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open('knowledge_base.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Successfully saved {len(products)} products to knowledge_base.json")
    print(f"Total products found: {len(product_urls)}")

if __name__ == "__main__":
    main()
