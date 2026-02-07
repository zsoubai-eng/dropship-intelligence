
import asyncio
import csv
import os
from supplier_validator import SupplierValidator

async def main():
    input_file = 'aliexpress_equivalents.csv'
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found.")
        return

    print(f"Reading products from {input_file}...")
    products = []
    with open(input_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            url = row.get('aliexpress_url', '').strip()
            if url and 'aliexpress' in url:
                products.append({
                    'title': row.get('original_title', ''),
                    'price': row.get('original_price', ''),
                    'url': url,
                    'keyword': row.get('keyword', '')
                })

    if not products:
        print("No valid AliExpress URLs found in the file.")
        return

    print(f"Found {len(products)} products to validate.")
    
    # Initialize validator
    validator = SupplierValidator()
    
    # Run validation
    await validator.validate_all_products(products)
    
    # Save results
    validator.save_validated_suppliers('validated_suppliers.csv')

if __name__ == "__main__":
    asyncio.run(main())
