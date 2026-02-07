#!/usr/bin/env python3
"""Extract AliExpress URLs from validate_suppliers_complete.py output or create from CSV"""

import csv
import re

# Read potential_winners.csv and create a simple aliexpress_equivalents.csv
# We'll use the keyword to construct search URLs for now

products = []
with open('potential_winners.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        title = row.get('title', '').strip()
        url = row.get('url', '')
        keyword = row.get('keyword', '').strip()
        
        if title and title != 'Sponsored ' and 'amazon.com' in url and keyword:
            # Create a search URL that Apify can use
            # For now, we'll create placeholder URLs that can be updated
            search_term = keyword.replace(' ', '+')
            aliexpress_search_url = f"https://www.aliexpress.com/wholesale?SearchText={search_term}"
            
            products.append({
                'original_title': title,
                'original_url': url,
                'original_price': row.get('price', ''),
                'keyword': keyword,
                'aliexpress_url': aliexpress_search_url,  # This will need actual product URLs
                'alternative_urls': ''
            })

# For now, let's use a simpler approach - extract from validate_suppliers_complete if it ran
# Or create a minimal version with search terms

if products:
    with open('aliexpress_equivalents.csv', 'w', newline='', encoding='utf-8') as f:
        fieldnames = ['original_title', 'original_url', 'original_price', 'keyword', 
                     'aliexpress_url', 'alternative_urls']
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(products[:10])  # Just first 10 for testing
    
    print(f"Created aliexpress_equivalents.csv with {len(products[:10])} products (search URLs)")
    print("Note: These are search URLs. We need actual product URLs from AliExpress.")
else:
    print("No products found")

