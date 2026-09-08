#!/usr/bin/env python3
"""
Test script to scrape first 2 pages quickly
"""

import sys
sys.path.insert(0, '/opt/goinfre/ayeshacy/Applications/OpenCode_projects/ai-seller')

from scrape_full_catalog_v2 import (
    get_product_urls_from_page,
    scrape_product_page,
    BASE_URL,
    CATALOG_URL,
    HEADERS
)
import time

print("Testing product URL extraction from first 2 pages...")

all_urls = []
seen = set()

for page_num in range(1, 3):
    if page_num == 1:
        page_url = CATALOG_URL
    else:
        page_url = f"{CATALOG_URL}page/{page_num}/"
    
    print(f"\nProcessing page {page_num}/2...")
    product_urls = get_product_urls_from_page(page_url)
    
    for url in product_urls:
        if url not in seen:
            seen.add(url)
            all_urls.append(url)
    
    time.sleep(1)

print(f"\n✓ Found {len(all_urls)} unique product URLs from 2 pages")

# Test scraping first 3 products
print("\nTesting product scraping (first 3 products)...")
products = []
for i, url in enumerate(all_urls[:3], 1):
    print(f"\nProcessing product {i}/3...")
    product_data = scrape_product_page(url)
    
    if product_data:
        products.append(product_data)
    
    time.sleep(1)

print(f"\n✓ Successfully scraped {len(products)} products")

# Print sample product
if products:
    print("\nSample product data:")
    import json
    print(json.dumps(products[0], indent=2, ensure_ascii=False))
