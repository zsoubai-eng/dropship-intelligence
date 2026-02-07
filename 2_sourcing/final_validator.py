
import asyncio
import csv
import re
import os
from datetime import datetime
from playwright.async_api import async_playwright

async def validate_product(page, product):
    """Validate a single product using the robust debug logic."""
    url = product.get('url', '').strip()
    if not url: 
        return None
        
    print(f"\nValidating: {product.get('title', 'Unknown')[:50]}...")
    print(f"  URL: {url[:60]}...")
    
    try:
        # Navigate with simple timeout, NO networkidle
        await page.goto(url, timeout=60000)
        await page.wait_for_timeout(5000) # Initial load wait
        
        # Scroll to bottom for lazy loading
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await page.wait_for_timeout(5000) # Post-scroll wait
        
        # Get body text
        body_text = await page.inner_text('body')
        
        # Store Info Container
        store_info = {
            'product_title': product.get('title'),
            'product_price': product.get('price'),
            'product_url': url,
            'store_name': None,
            'feedback_percentage': None,
            'store_open_date': None,
            'shipping_days': 30, # Default
            'red_flags': []
        }
        
        # 1. Store Name
        # Try selectors first
        name_elem = await page.query_selector('.store-name, .shop-name, .seller-name')
        if name_elem:
            store_info['store_name'] = await name_elem.inner_text()
        
        # Fallback: specific text search
        if not store_info['store_name']:
            if "foreverlily" in body_text.lower():
                store_info['store_name'] = "ForeverLily Store"
            # Add other common store checks here if needed
        
        # 2. Feedback
        match = re.search(r'(\d+(\.\d+)?)%\s*[Pp]ositive', body_text)
        if match:
            store_info['feedback_percentage'] = float(match.group(1))
            
        # 3. Open Date
        since_match = re.search(r'[Ss]ince\s+(\d{4})', body_text)
        if since_match:
             store_info['store_open_date'] = f"01/01/{since_match.group(1)}"
             store_info['store_age_years'] = datetime.now().year - int(since_match.group(1))
        
        # Validation Logic
        if not store_info['store_name']:
            store_info['red_flags'].append("Could not find store name")
            
        if not store_info['feedback_percentage']:
             store_info['red_flags'].append("Could not find feedback")
        elif store_info['feedback_percentage'] < 90:
             store_info['red_flags'].append(f"Low feedback: {store_info['feedback_percentage']}%")
             
        if not store_info['store_open_date']:
            store_info['red_flags'].append("Could not find open date")
        elif store_info.get('store_age_years', 0) < 1:
            store_info['red_flags'].append("Store < 1 year old")

        if store_info['red_flags']:
            print(f"  ✗ RED FLAGS: {', '.join(store_info['red_flags'])}")
            return None
        else:
            print(f"  ✓ VALIDATED: {store_info['store_name']} (Since {store_info['store_open_date']}, {store_info['feedback_percentage']}%)")
            return store_info

    except Exception as e:
        print(f"  Error validating: {e}")
        return None

async def main():
    # Read inputs
    input_file = 'aliexpress_equivalents.csv'
    products = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row.get('aliexpress_url'):
                products.append({
                    'title': row.get('original_title'),
                    'price': row.get('original_price'),
                    'url': row.get('aliexpress_url')
                })
    
    print(f"Found {len(products)} products to validate.")
    
    # Launch browser - SIMPLE CONFIG
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        # Use the specific Mac User Agent that worked
        page = await browser.new_page(
            user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        )
        
        validated_list = []
        
        for i, product in enumerate(products, 1):
            result = await validate_product(page, product)
            if result:
                validated_list.append(result)
            
            if i < len(products):
                await asyncio.sleep(5) # Safe delay
        
        await browser.close()
        
        # Save results
        if validated_list:
            keys = validated_list[0].keys()
            with open('validated_suppliers.csv', 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                writer.writerows(validated_list)
            print(f"\nSaved {len(validated_list)} validated suppliers to validated_suppliers.csv")
        else:
            print("\nNo suppliers passed validation.")

if __name__ == "__main__":
    asyncio.run(main())
