#!/usr/bin/env python3
"""
Complete Supplier Validation Workflow
1. Reads potential_winners.csv (with Amazon URLs)
2. Finds AliExpress equivalents
3. Validates suppliers (store age, feedback, shipping)
4. Outputs validated_suppliers.csv with only approved suppliers
"""

import csv
import asyncio
import re
import random
import os
from datetime import datetime
from typing import Dict, List, Optional
from playwright.async_api import async_playwright, Page
import sys

# Import rate limiting config
from rate_limit_config import RateLimitConfig

# Import validation logic from supplier_validator
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from supplier_validator import SupplierValidator
except ImportError:
    print("Error: Could not import SupplierValidator. Make sure supplier_validator.py is in the same directory.")
    sys.exit(1)


class CompleteValidator(SupplierValidator):
    """Extended validator that can find AliExpress equivalents first and log them."""

    def __init__(self):
        super().__init__()
        self.equivalents_csv = "aliexpress_equivalents.csv"

    def append_equivalent(self, product: Dict, aliexpress_url: str):
        """Append a found AliExpress equivalent to CSV (for Apify later)."""
        fieldnames = [
            "original_title",
            "original_url",
            "original_price",
            "keyword",
            "aliexpress_url",
            "source",
        ]
        file_exists = os.path.exists(self.equivalents_csv)
        with open(self.equivalents_csv, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()
            writer.writerow(
                {
                    "original_title": product.get("title", ""),
                    "original_url": product.get("url", ""),
                    "original_price": product.get("price", ""),
                    "keyword": product.get("keyword", ""),
                    "aliexpress_url": aliexpress_url,
                    "source": "validator",
                }
            )

    async def find_aliexpress_equivalent(
        self, page: Page, product_title: str, keyword: str = "", retry_count: int = 0
    ) -> Optional[str]:
        """Find AliExpress equivalent for an Amazon product."""
        # Use keyword if available, otherwise extract from title
        if keyword:
            search_query = keyword
        else:
            # Extract key terms (remove common words)
            words = product_title.split()
            filtered = [w for w in words[:6] if len(w) > 3 and w.lower() not in ['for', 'the', 'and', 'with', 'face']]
            search_query = ' '.join(filtered[:4])
        
        try:
            search_url = f"https://www.aliexpress.com/wholesale?SearchText={search_query.replace(' ', '+')}"
            
            # Add random delay before request
            delay = RateLimitConfig.get_random_delay()
            await asyncio.sleep(delay)
            
            await page.goto(search_url, wait_until="networkidle", timeout=60000)
            
            # Random delay after page load
            await page.wait_for_timeout(int(RateLimitConfig.PAGE_LOAD_DELAY * 1000))
            
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
            
            # Find first valid product link
            product_links = await page.query_selector_all('a[href*="/item/"]')
            
            for link in product_links[:10]:
                try:
                    href = await link.get_attribute("href")
                    if not href:
                        continue
                    href = href.split("?")[0]

                    # Normalize different href formats
                    if href.startswith("//"):
                        # Protocol-relative URL
                        return f"https:{href}"
                    elif href.startswith("http"):
                        return href
                    elif href.startswith("/"):
                        return f"https://www.aliexpress.com{href}"
                except:
                    continue
            
            return None
        
        except Exception as e:
            print(f"    Error finding equivalent: {e}")
            
            # Retry logic with exponential backoff
            if retry_count < RateLimitConfig.MAX_RETRIES:
                retry_delay = RateLimitConfig.get_retry_delay(retry_count)
                print(f"    Retrying in {retry_delay} seconds... (attempt {retry_count + 1}/{RateLimitConfig.MAX_RETRIES})")
                await asyncio.sleep(retry_delay)
                return await self.find_aliexpress_equivalent(page, product_title, keyword, retry_count + 1)
            
            return None
    
    async def process_amazon_product(self, page: Page, product: Dict) -> Optional[Dict]:
        """Process an Amazon product: find AliExpress equivalent and validate."""
        print(f"\nProcessing: {product.get('title', 'Unknown')[:60]}...")
        
        # Step 1: Find AliExpress equivalent
        print("  Step 1: Finding AliExpress equivalent...")
        aliexpress_url = await self.find_aliexpress_equivalent(
            page, 
            product.get('title', ''),
            product.get('keyword', '')
        )
        
        if not aliexpress_url:
            print("  ✗ Could not find AliExpress equivalent")
            return None
        
        print(f"  ✓ Found: {aliexpress_url[:80]}...")
        # Log equivalent for later Apify scraping
        self.append_equivalent(product, aliexpress_url)
        
        # Step 2: Validate supplier
        print("  Step 2: Validating supplier...")
        
        # Create product dict with AliExpress URL
        aliexpress_product = product.copy()
        aliexpress_product['url'] = aliexpress_url
        
        # Validate using parent class method
        validated = await self.validate_product(page, aliexpress_product)
        
        return validated


async def main():
    """Main workflow."""
    print("=" * 70)
    print("COMPLETE SUPPLIER VALIDATION WORKFLOW")
    print("=" * 70)
    print("\nThis script will:")
    print("1. Read products from potential_winners.csv")
    print("2. Find AliExpress equivalents for Amazon products")
    print("3. Validate suppliers (store age, feedback, shipping)")
    print("4. Save only validated suppliers to validated_suppliers.csv\n")
    
    # Read products from CSV
    products = []
    try:
        with open('potential_winners.csv', 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                title = row.get('title', '').strip()
                url = row.get('url', '')
                
                # Filter valid products
                if (title and 
                    title != 'Sponsored ' and 
                    url and 
                    url != 'N/A' and 
                    'javascript:void' not in url):
                    products.append({
                        'title': title,
                        'url': url,
                        'price': row.get('price', ''),
                        'keyword': row.get('keyword', ''),
                        'reviews': row.get('reviews', ''),
                        'rating': row.get('rating', '')
                    })
    except FileNotFoundError:
        print("Error: potential_winners.csv not found!")
        return
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return
    
    if not products:
        print("No products found in CSV!")
        return
    
    print(f"Found {len(products)} products to process")
    print(f"Processing all {len(products)} products (with adaptive delays and cooldowns)...\n")
    
    # Process all products
    products_to_process = products
    
    # Initialize validator
    validator = CompleteValidator()
    
    # Configure rate limiting (balanced by default, then override delays to 5–10s)
    RateLimitConfig.MIN_DELAY = 5
    RateLimitConfig.MAX_DELAY = 10
    print("\nRate Limiting Configuration:")
    print(f"  Mode: Balanced (3-8 second delays)")
    print(f"  Max Retries: {RateLimitConfig.MAX_RETRIES}")
    print(f"  User Agent Rotation: Enabled")
    print("\nTo change settings, edit rate_limit_config.py or use:")
    print("  - RateLimitConfig.configure_for_conservative()  # Safer (5-12s delays)")
    print("  - RateLimitConfig.configure_for_aggressive()   # Faster (2-4s delays, higher risk)")
    print()
    
    # Process products
    async with async_playwright() as p:
        # Get random user agent
        user_agent = RateLimitConfig.get_random_user_agent()
        
        # Configure browser context
        context_options = {
            'user_agent': user_agent,
            'viewport': {'width': 1920, 'height': 1080},
            'locale': 'en-US',
            'timezone_id': 'America/New_York',
        }
        
        # Add proxy if configured
        proxy = RateLimitConfig.get_random_proxy()
        if proxy:
            context_options['proxy'] = {'server': proxy}
            print(f"Using proxy: {proxy}")
        
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(**context_options)
        page = await context.new_page()
        
        for i, product in enumerate(products_to_process, 1):
            print(f"\nProcessing product {i} of {len(products_to_process)}...")
            print(f"Title: {product.get('title', '')[:80]}")
            
            try:
                # Check if it's already an AliExpress/CJ URL
                if validator.is_aliexpress_url(product['url']) or validator.is_cj_dropshipping_url(product['url']):
                    # Direct validation
                    await validator.validate_product(page, product)
                else:
                    # Find equivalent and validate
                    await validator.process_amazon_product(page, product)
            except Exception as e:
                print(f"  ERROR processing product {i}/{len(products_to_process)}: {e}")
            
            # Adaptive delays
            if i < len(products_to_process):
                if i % 20 == 0:
                    # Cooldown every 20 products
                    print("  Cooldown: sleeping for 60 seconds to mimic human behavior...")
                    await asyncio.sleep(60)
                else:
                    delay = RateLimitConfig.get_random_delay()
                    print(f"  Waiting {delay:.1f} seconds before next product...")
                    await asyncio.sleep(delay)
            
            # Rotate user agent every 5 products (if not using proxy)
            if not proxy and i % 5 == 0:
                new_ua = RateLimitConfig.get_random_user_agent()
                await context.set_extra_http_headers({'User-Agent': new_ua})
                print(f"  Rotated user agent")
        
        await browser.close()
    
    # Save results
    validator.save_validated_suppliers('validated_suppliers.csv')
    
    print("\n" + "=" * 70)
    print("WORKFLOW COMPLETE")
    print("=" * 70)
    print(f"\nValidated Suppliers: {len(validator.validated_suppliers)}")
    print(f"Red Flagged: {len(validator.red_flags)}")
    
    if validator.validated_suppliers:
        print("\n✓ You can now use validated_suppliers.csv for your dropshipping business!")
    else:
        print("\n⚠ No suppliers passed validation. You may need to:")
        print("  - Adjust red flag criteria")
        print("  - Try different products")
        print("  - Manually verify some suppliers")


if __name__ == "__main__":
    asyncio.run(main())

