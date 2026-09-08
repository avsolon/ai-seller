#!/usr/bin/env python3
"""
Simple scraper for faraline.ru - collects product data from all 14 pages.
"""

import requests
from bs4 import BeautifulSoup
import re
import json
import time
from typing import List, Dict

BASE_URL = "https://faraline.ru"
CATALOG_URL = f"{BASE_URL}/shop-2/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}

def get_page_urls():
    """Get all 14 page URLs."""
    return [CATALOG_URL] + [f"{CATALOG_URL}page/{i}/" for i in range(2, 15)]

def extract_product_urls(page_url: str) -> List[str]:
    """Extract product URLs from a page."""
    try:
        response = requests.get(page_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        urls = []
        for link in soup.find_all('a', href=True):
            href = link['href']
            if href.startswith(f"{BASE_URL}/product/") and href not in urls:
                urls.append(href)
        return urls
    except Exception as e:
        print(f"Error on {page_url}: {e}")
        return []

def scrape_product(url: str) -> Dict:
    """Scrape a single product page."""
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Extract name
        name = soup.find('h1').get_text(strip=True) if soup.find('h1') else 'N/A'
        
        # Extract data from JavaScript
        scripts = soup.find_all('script')
        product_id = 'N/A'
        price = 'N/A'
        category = 'N/A'
        
        for script in scripts:
            if 'var item' in str(script):
                text = script.string
                if text:
                    match = re.search(r'var item = (\{.*?\});', text, re.DOTALL)
                    if match:
                        try:
                            item_data = json.loads(match.group(1))
                            product_id = str(item_data.get('product_id', 'N/A'))
                            price = str(item_data.get('price', 'N/A'))
                            if 'categories' in item_data and item_data['categories']:
                                category = item_data['categories'][0]
                        except:
                            pass
                break
        
        # Extract availability
        availability = 'N/A'
        avail_div = soup.find('div', class_='product-stock')
        if avail_div:
            availability = avail_div.get_text(strip=True)
        
        # Extract description
        description = 'N/A'
        desc_div = soup.find('div', class_='woocommerce-product-details__short-description')
        if desc_div:
            description = desc_div.get_text(strip=True)
        
        # Extract characteristics
        characteristics = {}
        table = soup.find('table', class_='woocommerce-product-attributes__table')
        if table:
            for row in table.find_all('tr', class_='woocommerce-product-attributes-item'):
                th = row.find('th', class_='woocommerce-product-attributes-item__label')
                td = row.find('td', class_='woocommerce-product-attributes-item__value')
                if th and td:
                    characteristics[th.get_text(strip=True)] = td.get_text(strip=True)
        
        return {
            'id': product_id,
            'name': name,
            'description': description,
            'price': price,
            'availability': availability,
            'category': category,
            'characteristics': characteristics,
            'url': url
        }
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None

def main():
    print("Scraping faraline.ru...")
    
    # Get all page URLs
    page_urls = get_page_urls()
    print(f"Found {len(page_urls)} pages to scrape")
    
    # Collect all product URLs
    all_product_urls = []
    for page_url in page_urls:
        print(f"Processing page: {page_url}")
        urls = extract_product_urls(page_url)
        all_product_urls.extend(urls)
        time.sleep(2)
    
    # Remove duplicates
    unique_urls = []
    seen = set()
    for url in all_product_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    print(f"\nFound {len(unique_urls)} unique products")
    
    # Scrape each product
    products = []
    for i, url in enumerate(unique_urls, 1):
        print(f"Scraping product {i}/{len(unique_urls)}...")
        product = scrape_product(url)
        if product:
            products.append(product)
        time.sleep(1)
    
    # Save results
    output = {
        "products": products,
        "total_products": len(products),
        "total_found": len(unique_urls),
        "source": "faraline.ru",
        "scraped_at": time.strftime("%Y-%m-%d %H:%M:%S")
    }
    
    with open('knowledge_base.json', 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)
    
    print(f"\n✓ Done! Saved {len(products)} products to knowledge_base.json")

if __name__ == "__main__":
    main()
