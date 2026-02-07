#!/usr/bin/env python3
"""
Find AliExpress Equivalents
Searches AliExpress for products similar to Amazon products in the CSV
"""

import csv
import asyncio
from playwright.async_api import async_playwright, Page
import re


async def search_aliexpress(page: Page, product_title: str, max_results: int = 5):
    """Search AliExpress for a product and return top results."""
    # Extract key terms from product title
    keywords = product_title.split()[:5]  # First 5 words
    search_query = ' '.join(keywords)
    
    try:
        # Search AliExpress
        search_url = f"https://www.aliexpress.com/wholesale?SearchText={search_query.replace(' ', '+')}"
        await page.goto(search_url, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)
        
        # Handle popups
        try:
            close_buttons = await page.query_selector_all('button, [class*="close"]')
            for btn in close_buttons[:2]:
                try:
                    await btn.click(timeout=2000)
                    await page.wait_for_timeout(500)
                except:
                    pass
        except:
            pass
        
        # Find product links
        product_links = await page.query_selector_all('a[href*="/item/"]')
        
        results = []
        seen_urls = set()
        
        for link in product_links[:max_results * 2]:  # Get more to filter
            try:
                href = await link.get_attribute('href')
                if href and '/item/' in href:
                    if href.startswith('/'):
                        full_url = f"https://www.aliexpress.com{href.split('?')[0]}"
                    else:
                        full_url = href.split('?')[0]
                    
                    if full_url not in seen_urls:
                        seen_urls.add(full_url)
                        results.append(full_url)
                        if len(results) >= max_results:
                            break
            except:
                continue
        
        return results[:max_results]
    
    except Exception as e:
        print(f"  Error searching AliExpress: {e}")
        return []


async def main():
    """Find AliExpress equivalents for products in CSV."""
    print("=" * 70)
    print("FINDING ALIEXPRESS EQUIVALENTS")
    print("=" * 70)
    
    # Read products from CSV
    products = []
    try:
        with open('potential_winners.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get('title', '').strip()
                url = row.get('url', '')
                # Only process valid Amazon products
                if title and title != 'Sponsored ' and 'amazon.com' in url:
                    products.append({
                        'title': title,
                        'url': url,
                        'price': row.get('price', ''),
                        'keyword': row.get('keyword', '')
                    })
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    print(f"\nFound {len(products)} Amazon products to find equivalents for\n")
    
    # Create output CSV with AliExpress URLs
    output_rows = []
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        )
        page = await context.new_page()
        
        for i, product in enumerate(products, 1):
            print(f"{i}/{len(products)}. Searching for: {product['title'][:60]}...")
            
            aliexpress_urls = await search_aliexpress(page, product['title'], max_results=3)
            
            if aliexpress_urls:
                # Use first result as primary
                output_rows.append({
                    'original_title': product['title'],
                    'original_url': product['url'],
                    'original_price': product['price'],
                    'keyword': product['keyword'],
                    'aliexpress_url': aliexpress_urls[0],
                    'alternative_urls': ' | '.join(aliexpress_urls[1:]) if len(aliexpress_urls) > 1 else ''
                })
                print(f"   ✓ Found {len(aliexpress_urls)} AliExpress equivalent(s)")
            else:
                print(f"   ✗ No equivalents found")
            
            await page.wait_for_timeout(3000)  # Rate limiting
        
        await browser.close()
    
    # Save to CSV
    if output_rows:
        with open('aliexpress_equivalents.csv', 'w', newline='', encoding='utf-8') as f:
            fieldnames = ['original_title', 'original_url', 'original_price', 'keyword', 
                         'aliexpress_url', 'alternative_urls']
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(output_rows)
        
        print(f"\n{'='*70}")
        print(f"✓ Saved {len(output_rows)} AliExpress equivalents to aliexpress_equivalents.csv")
        print(f"{'='*70}")
        print("\nNext step: Run supplier_validator.py with the aliexpress_equivalents.csv")
    else:
        print("\nNo AliExpress equivalents found.")


if __name__ == "__main__":
    asyncio.run(main())

