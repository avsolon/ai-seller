#!/usr/bin/env python3
"""
Scraper for faraline.ru - collects product data from "Светодиодные линзы" category (3 pages).
"""

import requests
from bs4 import BeautifulSoup
import json
import re
import time
from typing import List, Dict

BASE_URL = "https://faraline.ru"
CATEGORY_URL = f"{BASE_URL}/product-category/svetodiodnye-linzy-2/"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
}


def get_category_page_urls():
    """Get all 3 page URLs for the category."""
    return [CATEGORY_URL] + [f"{CATEGORY_URL}page/{i}/" for i in range(2, 4)]


def extract_product_urls(page_url: str) -> List[str]:
    """Extract product URLs from a category page."""
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
        
        name = soup.find('h1').get_text(strip=True) if soup.find('h1') else 'N/A'
        
        # Check if product belongs to "Светодиодные линзы" category
        if not re.search(r'светодиодн|би-лед|led|линз', name, re.IGNORECASE):
            return None
        
        # Exclude non-relevant products (герметики, переходные рамки)
        if re.search(r'герметик|переходн|рамк', name, re.IGNORECASE):
            return None
        
        scripts = soup.find_all('script')
        product_id = 'N/A'
        price = 'N/A'
        
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
                        except:
                            pass
                break
        
        availability = 'Нет в наличии'
        avail_div = soup.find('div', class_='product-stock')
        if avail_div:
            availability_text = avail_div.get_text(strip=True)
            if 'в наличии' in availability_text.lower():
                availability = 'В наличии'
        
        description = ''
        desc_div = soup.find('div', class_='woocommerce-product-details__short-description')
        if desc_div:
            description = desc_div.get_text(strip=True)
        
        characteristics = parse_characteristics_from_name(name)
        
        # Дополняем комплектацию из описания
        if 'комплект' in description.lower():
            # Извлекаем только информацию о комплектации
            comp_match = re.search(r'Цена за комплект\([^)]+\)', description)
            if comp_match:
                characteristics['комплектация'] = comp_match.group()
            else:
                characteristics['комплектация'] = 'Цена за комплект'
        
        table = soup.find('table', class_='woocommerce-product-attributes__table')
        if table:
            for row in table.find_all('tr', class_='woocommerce-product-attributes-item'):
                th = row.find('th', class_='woocommerce-product-attributes-item__label')
                td = row.find('td', class_='woocommerce-product-attributes-item__value')
                if th and td:
                    key = th.get_text(strip=True).lower()
                    value = td.get_text(strip=True)
                    if key == 'модель':
                        characteristics['модель'] = value
                    elif key == 'размер':
                        characteristics['размер'] = value
                    elif key == 'напряжение':
                        characteristics['напряжение'] = value
                    elif 'цветовая температура' in key:
                        characteristics['цветовая_температура'] = value
                    elif key == 'мощность':
                        characteristics['мощность'] = value
                    elif key == 'комплектация':
                        characteristics['комплектация'] = value
        
        return {
            'id': product_id,
            'name': name,
            'description': description,
            'price': int(price) if price.isdigit() else 0,
            'availability': availability,
            'category': 'Светодиодные линзы',
            'characteristics': characteristics,
            'url': url
        }
    except Exception as e:
        print(f"Error scraping {url}: {e}")
        return None


def parse_characteristics_from_name(name: str) -> Dict:
    """Parse characteristics from product name."""
    characteristics = {
        'модель': '',
        'размер': '',
        'напряжение': '',
        'цветовая_температура': '',
        'мощность': '',
        'комплектация': '',
        'особенности': ''
    }
    
    # Убираем лишние слова из названия для парсинга
    clean_name = name.replace('Светодиодные би-лед модули ', '')
    clean_name = clean_name.replace('Светодиодные матричные би-лед модули ', '')
    
    # Размер (1.5", 2.5", 3") - ищем в оригинальном названии
    # Пробуем разные варианты символа дюйма: " (кавычка), ″ (знак дюйма), &#8243; (HTML-сущность)
    size_match = re.search(r'(\d+\.?\d*)(?:"|″|&#8243;)', name)
    if size_match:
        characteristics['размер'] = size_match.group(1) + '"'
    
    # Модель (ORIONLIGHT ALIEN, etc.) - ищем до размера или напряжения
    # Убираем размер (включая HTML-сущности), напряжение, мощность, температуру и особенности из clean_name
    temp_clean = re.sub(r'\d+\.?\d*(?:"|″|&#8243;)', '', clean_name)  # Убираем размер
    temp_clean = re.sub(r'\d+V', '', temp_clean)  # Убираем напряжение
    temp_clean = re.sub(r'\d+W', '', temp_clean)  # Убираем мощность
    temp_clean = re.sub(r'\d+K', '', temp_clean)  # Убираем температуру
    # Убираем особенности
    temp_clean = re.sub(r'\s+со\s+встроенной\s+обманкой.*', '', temp_clean, flags=re.IGNORECASE)
    temp_clean = re.sub(r'\s+с\s+шагренью', '', temp_clean, flags=re.IGNORECASE)
    temp_clean = re.sub(r'\s+для\s+\w+', '', temp_clean, flags=re.IGNORECASE)
    temp_clean = re.sub(r'\s+СТГ', '', temp_clean, flags=re.IGNORECASE)
    temp_clean = re.sub(r'\s+левый\s+руль', '', temp_clean, flags=re.IGNORECASE)
    temp_clean = re.sub(r'\s+прямая', '', temp_clean, flags=re.IGNORECASE)
    temp_clean = re.sub(r'\s+', ' ', temp_clean).strip()  # Убираем лишние пробелы
    
    # Ищем модель как ORIONLIGHT + слова до конца
    model_match = re.search(r'(ORIONLIGHT[\s\w()]+)', temp_clean, re.IGNORECASE)
    if not model_match:
        model_match = re.search(r'(ORIONLIGHT\s+\w+)', temp_clean, re.IGNORECASE)
    if not model_match:
        # Пробуем извлечь модель из оригинального названия (например, PL3-24)
        model_match = re.search(r'\(([A-Z0-9\-]+)\)', name)
        if model_match:
            characteristics['модель'] = model_match.group(1)
        else:
            # Если модели нет, используем часть названия до размера
            model_match = re.search(r'^(Светодиодные\s+(?:би-лед|матричные\s+би-лед)\s+модули\s+)(.+?)(?=\s+\d+\.?\d*(?:"|″|&#8243;))', name, re.IGNORECASE)
            if model_match:
                characteristics['модель'] = model_match.group(2).strip()
    if model_match and characteristics['модель'] == '':
        model = model_match.group(1).strip()
        characteristics['модель'] = model
    
    # Напряжение (12V, 24V)
    voltage_match = re.search(r'(\d+V)', name)
    if voltage_match:
        characteristics['напряжение'] = voltage_match.group(1)
    
    # Цветовая температура (5000K, 5500K, 6000K)
    temp_match = re.search(r'(\d+K)', name)
    if temp_match:
        characteristics['цветовая_температура'] = temp_match.group(1)
    
    # Мощность (50W, 60W) - берем первую мощность
    power_match = re.search(r'(\d+W)', name)
    if power_match:
        characteristics['мощность'] = power_match.group(1)
    
    # Комплектация
    characteristics['комплектация'] = ''
    
    # Особенности
    features = []
    if 'со встроенной обманкой' in name.lower():
        features.append('со встроенной обманкой')
    if 'с шагренью' in name.lower():
        features.append('с шагренью')
    if 'без четкой стг' in name.lower():
        features.append('без четкой СТГ')
    if 'левый руль' in name.lower():
        features.append('левый руль')
    if 'прямая' in name.lower():
        features.append('прямая')
    if '(3 чипа и 3 отражателя)' in name.lower():
        features.append('3 чипа и 3 отражателя')
    if '(gen 1)' in name.lower():
        features.append('GEN 1')
    if '(gen2)' in name.lower():
        features.append('GEN2')
    
    characteristics['особенности'] = ', '.join(features) if features else ''
    
    return characteristics


def main():
    print("Парсинг категории 'Светодиодные линзы'...")
    
    page_urls = get_category_page_urls()
    print(f"Найдено {len(page_urls)} страниц для парсинга")
    
    all_product_urls = []
    for page_url in page_urls:
        print(f"Обработка страницы: {page_url}")
        urls = extract_product_urls(page_url)
        all_product_urls.extend(urls)
        time.sleep(2)
    
    unique_urls = []
    seen = set()
    for url in all_product_urls:
        if url not in seen:
            seen.add(url)
            unique_urls.append(url)
    
    print(f"Найдено {len(unique_urls)} уникальных товаров")
    
    products = []
    for i, url in enumerate(unique_urls, 1):
        print(f"Парсинг товара {i}/{len(unique_urls)}: {url}")
        product = scrape_product(url)
        if product:
            products.append(product)
        time.sleep(1)
    
    with open('svetodiodnye_linzy.json', 'w', encoding='utf-8') as f:
        json.dump(products, f, ensure_ascii=False, indent=2)
    
    print(f"\nГотово! Сохранено {len(products)} товаров в svetodiodnye_linzy.json")


if __name__ == "__main__":
    main()
