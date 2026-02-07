#!/usr/bin/env python3
"""
Beauty & Skincare Product Scraper
Scrapes AliExpress and Amazon Best Sellers to find winning products
"""

import asyncio
import csv
import re
from typing import List, Dict, Optional
from playwright.async_api import async_playwright, Page, Browser
import time


class ProductScraper:
    """Scrapes product data from AliExpress and Amazon."""
    
    def __init__(self):
        self.products = []
        self.keywords = [
            "LED face mask",
            "skincare device",
            "beauty tool",
            "facial massager",
            "jade roller",
            "gua sha",
            "microcurrent device",
            "red light therapy",
            "skincare set",
            "beauty gadget"
        ]
    
    def calculate_opportunity_score(self, orders: int, reviews: int, rating: float = 0) -> float:
        """
        Calculate opportunity score based on:
        - High Demand: Orders > 500
        - Low Competition: Reviews < 100
        - Good Rating: Rating >= 4.0
        
        Returns score from 0-100
        """
        score = 0.0
        
        # High demand component (0-50 points)
        if orders > 10000:
            score += 50
        elif orders > 5000:
            score += 40
        elif orders > 1000:
            score += 30
        elif orders > 500:
            score += 20
        elif orders > 100:
            score += 10
        
        # Low competition component (0-30 points)
        if reviews < 50:
            score += 30
        elif reviews < 100:
            score += 20
        elif reviews < 500:
            score += 10
        elif reviews < 1000:
            score += 5
        
        # Rating component (0-20 points)
        if rating >= 4.5:
            score += 20
        elif rating >= 4.0:
            score += 15
        elif rating >= 3.5:
            score += 10
        elif rating >= 3.0:
            score += 5
        
        # Bonus: High demand + Low competition combo
        if orders > 500 and reviews < 100:
            score += 10
        
        return min(100.0, score)
    
    def parse_price(self, price_text: str) -> Optional[float]:
        """Parse price from text string."""
        if not price_text:
            return None
        
        # Remove currency symbols and extract numbers
        price_text = price_text.replace(',', '').replace('$', '').replace('€', '').replace('£', '')
        # Extract first number found
        match = re.search(r'(\d+\.?\d*)', price_text)
        if match:
            try:
                return float(match.group(1))
            except:
                return None
        return None
    
    def parse_number(self, text: str) -> int:
        """Parse number from text (handles K, M suffixes)."""
        if not text:
            return 0
        
        text = text.strip().replace(',', '').upper()
        
        # Handle K (thousands) and M (millions)
        if 'K' in text:
            try:
                return int(float(text.replace('K', '')) * 1000)
            except:
                return 0
        elif 'M' in text:
            try:
                return int(float(text.replace('M', '')) * 1000000)
            except:
                return 0
        else:
            # Extract first number
            match = re.search(r'(\d+)', text)
            if match:
                try:
                    return int(match.group(1))
                except:
                    return 0
        return 0
    
    def parse_rating(self, rating_text: str) -> float:
        """Parse rating from text."""
        if not rating_text:
            return 0.0
        
        # Extract first decimal number
        match = re.search(r'(\d+\.?\d*)', rating_text)
        if match:
            try:
                rating = float(match.group(1))
                # Normalize if rating is out of 5
                if rating > 5:
                    rating = rating / 2  # Assume out of 10
                return min(5.0, max(0.0, rating))
            except:
                return 0.0
        return 0.0
    
    async def scrape_aliexpress(self, page: Page, keyword: str, max_products: int = 20) -> List[Dict]:
        """Scrape products from AliExpress."""
        print(f"Scraping AliExpress for: {keyword}")
        products = []
        
        try:
            # Navigate to AliExpress search
            search_url = f"https://www.aliexpress.com/wholesale?SearchText={keyword.replace(' ', '+')}"
            await page.goto(search_url, wait_until="networkidle", timeout=60000)
            
            # Wait for products to load
            await page.wait_for_timeout(3000)
            
            # Handle potential popups/cookies
            try:
                # Try to close any popups
                close_buttons = await page.query_selector_all('button, [class*="close"], [class*="dismiss"]')
                for btn in close_buttons[:3]:  # Try first 3 close buttons
                    try:
                        await btn.click(timeout=2000)
                        await page.wait_for_timeout(500)
                    except:
                        pass
            except:
                pass
            
            # Scroll to load more products
            for i in range(3):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
            
            # Find product cards
            product_cards = await page.query_selector_all('[class*="product-card"], [class*="list--gallery"], [data-widget-cid]')
            
            if not product_cards:
                # Try alternative selectors
                product_cards = await page.query_selector_all('a[href*="/item/"]')
            
            print(f"Found {len(product_cards)} product cards")
            
            for card in product_cards[:max_products]:
                try:
                    product_data = {}
                    
                    # Extract title
                    title_elem = await card.query_selector('[class*="title"], h1, h2, h3, [class*="product-title"]')
                    if title_elem:
                        product_data['title'] = await title_elem.inner_text()
                    else:
                        title_attr = await card.get_attribute('title')
                        product_data['title'] = title_attr or "N/A"
                    
                    # Extract price
                    price_elem = await card.query_selector('[class*="price"], [class*="price-current"], [class*="price-value"]')
                    if price_elem:
                        price_text = await price_elem.inner_text()
                        product_data['price'] = self.parse_price(price_text)
                    else:
                        product_data['price'] = None
                    
                    # Extract orders
                    orders_elem = await card.query_selector('[class*="order"], [class*="sold"], [class*="sales"]')
                    if orders_elem:
                        orders_text = await orders_elem.inner_text()
                        product_data['orders'] = self.parse_number(orders_text)
                    else:
                        product_data['orders'] = 0
                    
                    # Extract rating
                    rating_elem = await card.query_selector('[class*="rating"], [class*="star"], [class*="score"]')
                    if rating_elem:
                        rating_text = await rating_elem.inner_text()
                        product_data['rating'] = self.parse_rating(rating_text)
                    else:
                        product_data['rating'] = 0.0
                    
                    # Extract reviews count
                    reviews_elem = await card.query_selector('[class*="review"], [class*="feedback"]')
                    if reviews_elem:
                        reviews_text = await reviews_elem.inner_text()
                        product_data['reviews'] = self.parse_number(reviews_text)
                    else:
                        product_data['reviews'] = 0
                    
                    # Get product URL
                    link_elem = await card.query_selector('a')
                    if link_elem:
                        href = await link_elem.get_attribute('href')
                        if href:
                            if href.startswith('/'):
                                product_data['url'] = f"https://www.aliexpress.com{href}"
                            else:
                                product_data['url'] = href
                        else:
                            product_data['url'] = "N/A"
                    else:
                        product_data['url'] = "N/A"
                    
                    product_data['source'] = 'AliExpress'
                    product_data['keyword'] = keyword
                    
                    # Calculate opportunity score
                    product_data['opportunity_score'] = self.calculate_opportunity_score(
                        product_data['orders'],
                        product_data['reviews'],
                        product_data['rating']
                    )
                    
                    if product_data['title'] and product_data['title'] != "N/A":
                        products.append(product_data)
                        print(f"  ✓ Found: {product_data['title'][:50]}... | Orders: {product_data['orders']} | Score: {product_data['opportunity_score']:.1f}")
                
                except Exception as e:
                    print(f"  ✗ Error extracting product: {e}")
                    continue
            
            # Rate limiting
            await page.wait_for_timeout(2000)
            
        except Exception as e:
            print(f"Error scraping AliExpress for {keyword}: {e}")
        
        return products
    
    async def scrape_amazon_bestsellers(self, page: Page, keyword: str, max_products: int = 20) -> List[Dict]:
        """Scrape products from Amazon Best Sellers."""
        print(f"Scraping Amazon Best Sellers for: {keyword}")
        products = []
        
        try:
            # Navigate to Amazon search
            search_url = f"https://www.amazon.com/s?k={keyword.replace(' ', '+')}&rh=n%3A3760901%2Cn%3A11055981"  # Beauty & Personal Care category
            await page.goto(search_url, wait_until="networkidle", timeout=60000)
            
            # Wait for products to load
            await page.wait_for_timeout(3000)
            
            # Handle potential captcha or sign-in prompts
            try:
                # Check for captcha
                if "captcha" in page.url.lower() or "robot" in page.url.lower():
                    print("  ⚠ Amazon may have detected automation. Continuing anyway...")
            except:
                pass
            
            # Scroll to load more products
            for i in range(2):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(2000)
            
            # Find product containers
            product_containers = await page.query_selector_all('[data-component-type="s-search-result"]')
            
            if not product_containers:
                # Try alternative selector
                product_containers = await page.query_selector_all('[class*="s-result-item"]')
            
            print(f"Found {len(product_containers)} product containers")
            
            for container in product_containers[:max_products]:
                try:
                    product_data = {}
                    
                    # Extract title
                    title_elem = await container.query_selector('h2 a span, [data-cy="title-recipe"] span, .s-title-instructions-style span')
                    if title_elem:
                        product_data['title'] = await title_elem.inner_text()
                    else:
                        title_link = await container.query_selector('h2 a')
                        if title_link:
                            product_data['title'] = await title_link.inner_text()
                        else:
                            product_data['title'] = "N/A"
                    
                    # Extract price
                    price_elem = await container.query_selector('.a-price-whole, .a-offscreen, [class*="price"]')
                    if price_elem:
                        price_text = await price_elem.inner_text()
                        product_data['price'] = self.parse_price(price_text)
                    else:
                        # Try alternative price selector
                        price_alt = await container.query_selector('.a-price .a-offscreen')
                        if price_alt:
                            price_text = await price_alt.inner_text()
                            product_data['price'] = self.parse_price(price_text)
                        else:
                            product_data['price'] = None
                    
                    # Extract rating
                    rating_elem = await container.query_selector('[aria-label*="stars"], .a-icon-alt, [class*="rating"]')
                    if rating_elem:
                        rating_text = await rating_elem.inner_text()
                        product_data['rating'] = self.parse_rating(rating_text)
                    else:
                        product_data['rating'] = 0.0
                    
                    # Extract reviews count
                    reviews_elem = await container.query_selector('a[href*="#customerReviews"], [aria-label*="ratings"], [class*="review"]')
                    if reviews_elem:
                        reviews_text = await reviews_elem.inner_text()
                        product_data['reviews'] = self.parse_number(reviews_text)
                    else:
                        product_data['reviews'] = 0
                    
                    # Amazon doesn't show orders, use reviews as proxy
                    product_data['orders'] = product_data['reviews']  # Use reviews as proxy for demand
                    
                    # Get product URL
                    link_elem = await container.query_selector('h2 a, [data-cy="title-recipe"] a')
                    if link_elem:
                        href = await link_elem.get_attribute('href')
                        if href:
                            if href.startswith('/'):
                                product_data['url'] = f"https://www.amazon.com{href.split('?')[0]}"
                            else:
                                product_data['url'] = href.split('?')[0]
                        else:
                            product_data['url'] = "N/A"
                    else:
                        product_data['url'] = "N/A"
                    
                    product_data['source'] = 'Amazon'
                    product_data['keyword'] = keyword
                    
                    # Calculate opportunity score
                    # For Amazon, use reviews as both orders and reviews
                    product_data['opportunity_score'] = self.calculate_opportunity_score(
                        product_data['orders'],
                        product_data['reviews'],
                        product_data['rating']
                    )
                    
                    if product_data['title'] and product_data['title'] != "N/A":
                        products.append(product_data)
                        print(f"  ✓ Found: {product_data['title'][:50]}... | Reviews: {product_data['reviews']} | Score: {product_data['opportunity_score']:.1f}")
                
                except Exception as e:
                    print(f"  ✗ Error extracting product: {e}")
                    continue
            
            # Rate limiting
            await page.wait_for_timeout(2000)
            
        except Exception as e:
            print(f"Error scraping Amazon for {keyword}: {e}")
        
        return products
    
    async def scrape_all(self, max_products_per_keyword: int = 15):
        """Scrape all keywords from both sources."""
        print("=" * 70)
        print("BEAUTY & SKINCARE PRODUCT SCRAPER")
        print("=" * 70)
        print(f"\nScraping {len(self.keywords)} keywords...")
        print(f"Max products per keyword: {max_products_per_keyword}\n")
        
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch(headless=True)
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            page = await context.new_page()
            
            all_products = []
            
            for keyword in self.keywords:
                print(f"\n{'='*70}")
                print(f"Processing keyword: {keyword}")
                print(f"{'='*70}")
                
                # Scrape AliExpress
                aliexpress_products = await self.scrape_aliexpress(page, keyword, max_products_per_keyword)
                all_products.extend(aliexpress_products)
                
                # Wait between sources
                await page.wait_for_timeout(3000)
                
                # Scrape Amazon
                amazon_products = await self.scrape_amazon_bestsellers(page, keyword, max_products_per_keyword)
                all_products.extend(amazon_products)
                
                # Wait between keywords
                await page.wait_for_timeout(3000)
            
            await browser.close()
        
        # Remove duplicates based on title similarity
        unique_products = self.deduplicate_products(all_products)
        
        # Sort by opportunity score
        unique_products.sort(key=lambda x: x['opportunity_score'], reverse=True)
        
        self.products = unique_products
        return unique_products
    
    def deduplicate_products(self, products: List[Dict]) -> List[Dict]:
        """Remove duplicate products based on title similarity."""
        unique = []
        seen_titles = []
        
        for product in products:
            # Normalize title for comparison
            title_lower = product['title'].lower().strip()
            title_words = set(title_lower.split()[:5])  # First 5 words as key
            
            # Check if similar product already exists
            is_duplicate = False
            for seen in seen_titles:
                if len(title_words.intersection(seen)) >= 3:  # 3+ common words = duplicate
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique.append(product)
                seen_titles.append(title_words)
        
        return unique
    
    def save_to_csv(self, filename: str = 'potential_winners.csv'):
        """Save products to CSV file."""
        if not self.products:
            print("No products to save!")
            return
        
        fieldnames = ['title', 'price', 'orders', 'reviews', 'rating', 'opportunity_score', 'source', 'keyword', 'url']
        
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            for product in self.products:
                writer.writerow({
                    'title': product.get('title', 'N/A'),
                    'price': product.get('price', 'N/A'),
                    'orders': product.get('orders', 0),
                    'reviews': product.get('reviews', 0),
                    'rating': product.get('rating', 0.0),
                    'opportunity_score': round(product.get('opportunity_score', 0.0), 2),
                    'source': product.get('source', 'N/A'),
                    'keyword': product.get('keyword', 'N/A'),
                    'url': product.get('url', 'N/A')
                })
        
        print(f"\n{'='*70}")
        print(f"✓ Saved {len(self.products)} products to {filename}")
        print(f"{'='*70}")
        
        # Print top 10 products
        print("\nTOP 10 OPPORTUNITY SCORES:")
        print("-" * 70)
        for i, product in enumerate(self.products[:10], 1):
            print(f"{i}. {product['title'][:60]}")
            print(f"   Score: {product['opportunity_score']:.1f} | Orders: {product['orders']} | Reviews: {product['reviews']} | Price: ${product['price'] or 'N/A'}")
            print(f"   Source: {product['source']}")
            print()


async def main():
    """Main function."""
    import sys
    
    # Check for test mode
    test_mode = '--test' in sys.argv or '-t' in sys.argv
    
    scraper = ProductScraper()
    
    if test_mode:
        print("🧪 TEST MODE: Scraping only first keyword...")
        scraper.keywords = scraper.keywords[:1]
        max_products = 5
    else:
        max_products = 15
    
    # Scrape products
    products = await scraper.scrape_all(max_products_per_keyword=max_products)
    
    # Save to CSV
    scraper.save_to_csv('potential_winners.csv')
    
    print(f"\n{'='*70}")
    print("SUMMARY")
    print(f"{'='*70}")
    print(f"Total unique products found: {len(products)}")
    print(f"Products with score >= 50: {sum(1 for p in products if p['opportunity_score'] >= 50)}")
    print(f"Products with score >= 70: {sum(1 for p in products if p['opportunity_score'] >= 70)}")
    print(f"Products with score >= 80: {sum(1 for p in products if p['opportunity_score'] >= 80)}")
    
    # Breakdown by source
    aliexpress_count = sum(1 for p in products if p['source'] == 'AliExpress')
    amazon_count = sum(1 for p in products if p['source'] == 'Amazon')
    print(f"\nBy Source:")
    print(f"  AliExpress: {aliexpress_count} products")
    print(f"  Amazon: {amazon_count} products")


if __name__ == "__main__":
    asyncio.run(main())

