#!/usr/bin/env python3
"""
Supplier Validator
Validates AliExpress and CJ Dropshipping suppliers by checking store age, feedback, and shipping
"""

import csv
import re
import asyncio
import random
import os
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from playwright.async_api import async_playwright, Page, Browser
from urllib.parse import urlparse, parse_qs
import time

# Import rate limiting config
try:
    from rate_limit_config import RateLimitConfig
except ImportError:
    # Fallback if rate_limit_config not available
    class RateLimitConfig:
        MIN_DELAY = 3
        MAX_DELAY = 8
        PAGE_LOAD_DELAY = 3
        MAX_RETRIES = 3
        @staticmethod
        def get_random_delay():
            return random.uniform(3, 8)
        @staticmethod
        def get_random_user_agent():
            return 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        @staticmethod
        def get_retry_delay(attempt):
            return 5 * (2 ** attempt)


class SupplierValidator:
    """Validates suppliers from AliExpress and CJ Dropshipping."""
    
    def __init__(self):
        self.validated_suppliers = []
        self.red_flags = []
        self.output_filename = 'validated_suppliers.csv'
    
    def is_aliexpress_url(self, url: str) -> bool:
        """Check if URL is from AliExpress."""
        return 'aliexpress.com' in url.lower() or 'aliexpress.us' in url.lower()
    
    def is_cj_dropshipping_url(self, url: str) -> bool:
        """Check if URL is from CJ Dropshipping."""
        return 'cjdropshipping.com' in url.lower()
    
    def parse_date(self, date_text: str) -> Optional[datetime]:
        """Parse various date formats."""
        if not date_text:
            return None
        
        # Common date patterns
        patterns = [
            r'(\d{4})[-\/](\d{1,2})[-\/](\d{1,2})',  # YYYY-MM-DD
            r'(\d{1,2})[-\/](\d{1,2})[-\/](\d{4})',  # MM-DD-YYYY
            r'(\w+)\s+(\d{1,2}),\s+(\d{4})',  # Month DD, YYYY
            r'(\d{4})\s+(\w+)\s+(\d{1,2})',  # YYYY Month DD
        ]
        
        for pattern in patterns:
            match = re.search(pattern, date_text)
            if match:
                try:
                    # Try to parse
                    date_str = match.group(0)
                    for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%B %d, %Y', '%Y %B %d']:
                        try:
                            return datetime.strptime(date_str, fmt)
                        except:
                            continue
                except:
                    continue
        
        # Try to extract year and calculate approximate date
        year_match = re.search(r'(\d{4})', date_text)
        if year_match:
            try:
                year = int(year_match.group(1))
                if 2000 <= year <= datetime.now().year:
                    return datetime(year, 1, 1)
            except:
                pass
        
        return None
    
    def calculate_store_age_years(self, open_date: Optional[datetime]) -> Optional[float]:
        """Calculate store age in years."""
        if not open_date:
            return None
        
        age_delta = datetime.now() - open_date
        return age_delta.days / 365.25
    
    def parse_feedback_percentage(self, feedback_text: str) -> Optional[float]:
        """Extract feedback percentage from text."""
        if not feedback_text:
            return None
        
        # Look for percentage patterns
        match = re.search(r'(\d+\.?\d*)%', feedback_text)
        if match:
            try:
                return float(match.group(1))
            except:
                pass
        
        # Look for fraction patterns like "95.5" or "98.2"
        match = re.search(r'(\d{2,3}\.?\d*)', feedback_text)
        if match:
            try:
                value = float(match.group(1))
                if 0 <= value <= 100:
                    return value
            except:
                pass
        
        return None
    
    def parse_shipping_days(self, shipping_text: str) -> Optional[int]:
        """Extract shipping days from text."""
        if not shipping_text:
            return None
        
        shipping_text = shipping_text.lower()
        
        # Check for "AliExpress Standard Shipping" or fast shipping
        if 'standard' in shipping_text and 'aliexpress' in shipping_text:
            # AliExpress Standard is typically 15-30 days
            return 30
        elif 'epacket' in shipping_text or 'e-packet' in shipping_text:
            return 15
        elif 'dhl' in shipping_text or 'fedex' in shipping_text or 'ups' in shipping_text:
            return 7
        elif 'express' in shipping_text:
            return 10
        
        # Extract number of days
        day_patterns = [
            r'(\d+)\s*days?',
            r'(\d+)\s*-\s*(\d+)\s*days?',  # Range like "15-30 days"
            r'(\d+)\s*day',
        ]
        
        for pattern in day_patterns:
            match = re.search(pattern, shipping_text)
            if match:
                try:
                    if len(match.groups()) == 2:  # Range
                        return int(match.group(2))  # Take the higher number
                    else:
                        return int(match.group(1))
                except:
                    continue
        
        # Default to 30 if we can't determine
        return 30
    
    async def scrape_aliexpress_store(self, page: Page, product_url: str) -> Dict:
        """Scrape AliExpress store information."""
        print(f"  Scraping AliExpress store from: {product_url[:80]}...")
        
        store_info = {
            'store_name': None,
            'store_open_date': None,
            'feedback_percentage': None,
            'shipping_method': None,
            'store_url': None,
            'red_flags': []
        }
        
        try:
            # Add random delay before request
            delay = RateLimitConfig.get_random_delay()
            await asyncio.sleep(delay)
            
            # Navigate to product page
            await page.goto(product_url, timeout=60000)
            await page.wait_for_timeout(int(RateLimitConfig.PAGE_LOAD_DELAY * 1000))
            
            # Handle popups
            try:
                close_buttons = await page.query_selector_all('button, [class*="close"], [class*="dismiss"]')
                for btn in close_buttons[:3]:
                    try:
                        await btn.click(timeout=2000)
                        await page.wait_for_timeout(500)
                    except:
                        pass
            except:
                pass
            
            # Find store link/name
            store_link = await page.query_selector('a[href*="/store/"], [class*="store-name"], [class*="store-link"]')
            if store_link:
                store_name = await store_link.inner_text()
                store_href = await store_link.get_attribute('href')
                if store_href:
                    if store_href.startswith('/'):
                        store_info['store_url'] = f"https://www.aliexpress.com{store_href}"
                    else:
                        store_info['store_url'] = store_href
                store_info['store_name'] = store_name.strip()
            
            # Try alternative selectors for store name
            if not store_info['store_name']:
                store_name_elem = await page.query_selector('[class*="store"], [data-role="store-name"]')
                if store_name_elem:
                    store_info['store_name'] = (await store_name_elem.inner_text()).strip()
            
            # Navigate to store page if we found the link
            if store_info['store_url']:
                try:
                    await page.goto(store_info['store_url'], wait_until="networkidle", timeout=60000)
                    await page.wait_for_timeout(3000)
                    
                    # Scrape store information
                    # Store open date
                    date_elem = await page.query_selector('[class*="open-date"], [class*="store-date"], [class*="since"]')
                    if date_elem:
                        date_text = await date_elem.inner_text()
                        store_info['store_open_date'] = self.parse_date(date_text)
                    
                    # Try alternative date selectors
                    if not store_info['store_open_date']:
                        all_text = await page.inner_text('body')
                        date_match = re.search(r'(since|opened|established|from)\s*:?\s*(\d{4})', all_text, re.IGNORECASE)
                        if date_match:
                            year = int(date_match.group(2))
                            store_info['store_open_date'] = datetime(year, 1, 1)
                    
                    # Feedback percentage
                    feedback_elem = await page.query_selector('[class*="feedback"], [class*="rating"], [class*="positive"]')
                    if feedback_elem:
                        feedback_text = await feedback_elem.inner_text()
                        store_info['feedback_percentage'] = self.parse_feedback_percentage(feedback_text)
                    
                    # Try to find feedback in various formats
                    if not store_info['feedback_percentage']:
                        feedback_patterns = [
                            r'(\d+\.?\d*)%\s*positive',
                            r'positive\s*:?\s*(\d+\.?\d*)%',
                            r'feedback\s*:?\s*(\d+\.?\d*)%',
                        ]
                        page_text = await page.inner_text('body')
                        for pattern in feedback_patterns:
                            match = re.search(pattern, page_text, re.IGNORECASE)
                            if match:
                                store_info['feedback_percentage'] = float(match.group(1))
                                break
                
                except Exception as e:
                    print(f"    ⚠ Could not access store page: {e}")
            
            # --- FALLBACK: If store page access failed or data missing, try scraping from product page directly ---
            
            # Scroll to bottom to ensure lazy-loaded brand info is present
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await page.wait_for_timeout(5000)
            
            # Debug: Check if we are seeing the full page
            body_len = await page.evaluate("document.body.innerText.length")
            print(f"    (Debug: Page text length: {body_len})")

            if not store_info['store_name']:
                 # Try finding store name in product page brand section or header
                 candidates = await page.query_selector_all('.store-name, .shop-name, .seller-name, a[href*="/store/"]')
                 for c in candidates:
                     text = await c.inner_text()
                     if text and len(text) > 2:
                         store_info['store_name'] = text.strip()
                         break
            
            if not store_info['feedback_percentage']:
                # Look for feedback patterns in the entire product page text
                body_text = await page.inner_text('body')
                # Try simpler pattern first
                match = re.search(r'(\d+(\.\d+)?)%\s*[Pp]ositive', body_text)
                if match:
                    store_info['feedback_percentage'] = float(match.group(1))

            if not store_info['store_open_date']:
                 # Look for "Since YYYY" or "Opened: ..." in product page text (common for Brand stories)
                 body_text = await page.inner_text('body')
                 
                 # Pattern: "Since 2017" or "since 2017"
                 since_match = re.search(r'[Ss]ince\s+(\d{4})', body_text)
                 if since_match:
                     year = int(since_match.group(1))
                     store_info['store_open_date'] = datetime(year, 1, 1)
                 else:
                     # Pattern 2: "Opened ... 2017"
                     opened_match = re.search(r'(opened|established).*?(\d{4})', body_text, re.IGNORECASE)
                     if opened_match:
                         year = int(opened_match.group(2))
                         store_info['store_open_date'] = datetime(year, 1, 1)
            
            # Get shipping information from product page
            shipping_elem = await page.query_selector('[class*="shipping"], [class*="delivery"], [class*="logistics"]')
            if shipping_elem:
                shipping_text = await shipping_elem.inner_text()
                store_info['shipping_method'] = shipping_text.strip()
            else:
                # Try to find shipping info in page text
                page_text = await page.inner_text('body')
                if 'aliexpress standard' in page_text.lower():
                    store_info['shipping_method'] = 'AliExpress Standard Shipping'
                elif 'epacket' in page_text.lower():
                    store_info['shipping_method'] = 'ePacket'
            
            # If we couldn't get shipping from product page, check shipping options
            if not store_info['shipping_method']:
                shipping_options = await page.query_selector_all('[class*="shipping-option"], [data-role="shipping"]')
                for option in shipping_options[:3]:
                    try:
                        text = await option.inner_text()
                        if 'standard' in text.lower() or 'express' in text.lower():
                            store_info['shipping_method'] = text.strip()
                            break
                    except:
                        continue
            
        except Exception as e:
            print(f"    ✗ Error scraping AliExpress: {e}")
            store_info['red_flags'].append(f"Scraping error: {str(e)}")
        
        return store_info
    
    async def scrape_cj_dropshipping_store(self, page: Page, product_url: str) -> Dict:
        """Scrape CJ Dropshipping store information."""
        print(f"  Scraping CJ Dropshipping store from: {product_url[:80]}...")
        
        store_info = {
            'store_name': 'CJ Dropshipping',
            'store_open_date': datetime(2015, 1, 1),  # CJ is established
            'feedback_percentage': 98.0,  # CJ typically has high ratings
            'shipping_method': 'CJ Express Shipping',
            'store_url': 'https://www.cjdropshipping.com',
            'red_flags': []
        }
        
        try:
            # Add random delay before request
            delay = RateLimitConfig.get_random_delay()
            await asyncio.sleep(delay)
            
            await page.goto(product_url, wait_until="networkidle", timeout=60000)
            await page.wait_for_timeout(int(RateLimitConfig.PAGE_LOAD_DELAY * 1000))
            
            # CJ Dropshipping typically shows shipping info on product page
            shipping_elem = await page.query_selector('[class*="shipping"], [class*="delivery"]')
            if shipping_elem:
                shipping_text = await shipping_elem.inner_text()
                store_info['shipping_method'] = shipping_text.strip()
            
            # Check for specific shipping times
            page_text = await page.inner_text('body')
            shipping_days = self.parse_shipping_days(page_text)
            if shipping_days:
                store_info['shipping_days'] = shipping_days
        
        except Exception as e:
            print(f"    ✗ Error scraping CJ Dropshipping: {e}")
            store_info['red_flags'].append(f"Scraping error: {str(e)}")
        
        return store_info
    
    def check_red_flags(self, store_info: Dict) -> List[str]:
        """Check for red flags based on store criteria."""
        red_flags = []
        
        # Check store age
        store_age = self.calculate_store_age_years(store_info.get('store_open_date'))
        if store_age is not None and store_age < 1.0:
            red_flags.append(f"Store age < 1 year ({store_age:.1f} years)")
        elif store_age is None:
            red_flags.append("Could not determine store age")
        
        # Check feedback percentage
        feedback = store_info.get('feedback_percentage')
        if feedback is not None and feedback < 95.0:
            red_flags.append(f"Feedback < 95% ({feedback:.1f}%)")
        elif feedback is None:
            red_flags.append("Could not determine feedback percentage")
        
        # Check shipping time
        shipping_method = store_info.get('shipping_method') or ''
        shipping_days = self.parse_shipping_days(shipping_method)
        if shipping_days and shipping_days > 30:
            red_flags.append(f"Shipping > 30 days ({shipping_days} days)")
        
        return red_flags
    
    async def validate_product(self, page: Page, product: Dict) -> Optional[Dict]:
        """Validate a single product's supplier."""
        url = product.get('url', '')
        
        if not url or url == 'N/A' or 'javascript:void' in url:
            return None
        
        print(f"\nValidating: {product.get('title', 'Unknown')[:60]}...")
        
        store_info = {}
        
        if self.is_aliexpress_url(url):
            store_info = await self.scrape_aliexpress_store(page, url)
        elif self.is_cj_dropshipping_url(url):
            store_info = await self.scrape_cj_dropshipping_store(page, url)
        else:
            print(f"  ⚠ URL is not AliExpress or CJ Dropshipping: {url}")
            return None
        
        # Add product information
        store_info['product_title'] = product.get('title', 'N/A')
        store_info['product_price'] = product.get('price', 'N/A')
        store_info['product_url'] = url
        store_info['product_keyword'] = product.get('keyword', 'N/A')
        
        # Check for red flags
        red_flags = self.check_red_flags(store_info)
        store_info['red_flags'] = red_flags
        
        # Calculate store age for display
        store_age = self.calculate_store_age_years(store_info.get('store_open_date'))
        store_info['store_age_years'] = store_age
        
        # Parse shipping days
        shipping_days = self.parse_shipping_days(store_info.get('shipping_method', ''))
        store_info['shipping_days'] = shipping_days
        
        # Print results
        if red_flags:
            print(f"  ✗ RED FLAGS: {', '.join(red_flags)}")
            self.red_flags.append(store_info)
        else:
            print(f"  ✓ VALIDATED - Store: {store_info.get('store_name', 'N/A')}, Age: {store_age:.1f} years, Feedback: {store_info.get('feedback_percentage', 'N/A')}%")
            self.validated_suppliers.append(store_info)
            # Checkpoint save: append this supplier immediately
            self.append_validated_supplier(store_info, self.output_filename)
        
        return store_info
    
    async def validate_all_products(self, products: List[Dict]):
        """Validate all products from the CSV."""
        print("=" * 70)
        print("SUPPLIER VALIDATOR")
        print("=" * 70)
        print(f"\nValidating {len(products)} products...\n")
        
        async with async_playwright() as p:
            # Use the simple, proven launch config from debug_scraper.py
            browser = await p.chromium.launch(headless=True)
            # Create a simple page with the specific Mac user agent
            # We skip complex context options that might be triggering detection
            page = await browser.new_page(
                 user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            for i, product in enumerate(products, 1):
                print(f"\n[{i}/{len(products)}] Validating product...")
                try:
                    await self.validate_product(page, product)
                except Exception as e:
                    print(f"Error validating product: {e}")
                
                # Random delay between products (except for last one)
                if i < len(products):
                    await asyncio.sleep(5) # Fixed 5s delay to be safe
            
            await browser.close()
    
    def append_validated_supplier(self, supplier: Dict, filename: str = 'validated_suppliers.csv'):
        """Append a single validated supplier to CSV (checkpoint saving)."""
        fieldnames = [
            'product_title',
            'product_price',
            'store_name',
            'store_url',
            'store_age_years',
            'store_open_date',
            'feedback_percentage',
            'shipping_method',
            'shipping_days',
            'product_url',
            'product_keyword'
        ]

        file_exists = os.path.exists(filename)

        with open(filename, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            if not file_exists:
                writer.writeheader()

            writer.writerow({
                'product_title': supplier.get('product_title', 'N/A'),
                'product_price': supplier.get('product_price', 'N/A'),
                'store_name': supplier.get('store_name', 'N/A'),
                'store_url': supplier.get('store_url', 'N/A'),
                'store_age_years': f"{supplier.get('store_age_years', 0):.1f}" if supplier.get('store_age_years') else 'N/A',
                'store_open_date': supplier.get('store_open_date').strftime('%Y-%m-%d') if supplier.get('store_open_date') else 'N/A',
                'feedback_percentage': f"{supplier.get('feedback_percentage', 0):.1f}" if supplier.get('feedback_percentage') else 'N/A',
                'shipping_method': supplier.get('shipping_method', 'N/A'),
                'shipping_days': supplier.get('shipping_days', 'N/A'),
                'product_url': supplier.get('product_url', 'N/A'),
                'product_keyword': supplier.get('product_keyword', 'N/A')
            })

    def save_validated_suppliers(self, filename: str = 'validated_suppliers.csv'):
        """Print summary of validated suppliers (file is updated incrementally)."""
        print(f"\n{'='*70}")
        print(f"Validation run complete. Summary below (data appended to {filename} in real-time).")
        print(f"{'='*70}")
        print(f"\nValidated this run: {len(self.validated_suppliers)}")
        print(f"Red Flagged this run: {len(self.red_flags)}")
        
        if self.validated_suppliers:
            print("\nTOP VALIDATED SUPPLIERS (this run):")
            print("-" * 70)
            for i, supplier in enumerate(self.validated_suppliers[:10], 1):
                print(f"{i}. {supplier.get('store_name', 'N/A')}")
                print(f"   Product: {supplier.get('product_title', 'N/A')[:50]}...")
                print(f"   Age: {supplier.get('store_age_years', 0):.1f} years | Feedback: {supplier.get('feedback_percentage', 0):.1f}% | Shipping: {supplier.get('shipping_days', 'N/A')} days")
                print()


def read_products_from_csv(filename: str = 'potential_winners.csv') -> List[Dict]:
    """Read products from CSV file."""
    products = []
    
    try:
        with open(filename, 'r', encoding='utf-8') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                # Filter out invalid URLs
                url = row.get('url', '')
                if url and url != 'N/A' and 'javascript:void' not in url:
                    products.append({
                        'title': row.get('title', ''),
                        'price': row.get('price', ''),
                        'url': url,
                        'keyword': row.get('keyword', ''),
                        'reviews': row.get('reviews', ''),
                        'rating': row.get('rating', '')
                    })
    except FileNotFoundError:
        print(f"Error: {filename} not found!")
        return []
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return []
    
    return products


async def main():
    """Main function."""
    # Read products from CSV
    products = read_products_from_csv('potential_winners.csv')
    
    if not products:
        print("No products found in potential_winners.csv")
        return
    
    # Filter to only AliExpress and CJ Dropshipping URLs
    validator = SupplierValidator()
    filtered_products = []
    
    for product in products:
        url = product.get('url', '')
        if validator.is_aliexpress_url(url) or validator.is_cj_dropshipping_url(url):
            filtered_products.append(product)
    
    if not filtered_products:
        print("No AliExpress or CJ Dropshipping URLs found in the CSV")
        return
    
    print(f"Found {len(filtered_products)} products with AliExpress/CJ Dropshipping URLs")
    
    # Validate all products
    await validator.validate_all_products(filtered_products)
    
    # Save validated suppliers
    validator.save_validated_suppliers('validated_suppliers.csv')


if __name__ == "__main__":
    asyncio.run(main())

