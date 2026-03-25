import requests
import json

# CONFIG
API_KEY = "YOUR-API-KEY"
SITE_ID = "YOUR-SITE-ID"
BASE = f"https://api.cquotient.com/v3/personalization/recs/{SITE_ID}"
HEADERS = {"x-cq-client-id": API_KEY}

# replace with a real product ID to test product recommenders
test_product = "YOUR-PRODUCT-ID"

# test categories (from your master table)
categories = [
    ("CAT-ID-1", "Category 1"),
    ("CAT-ID-2", "Category 2"),
    ("CAT-ID-3", "Category 3"),
]

# recommenders
category_recommenders = [
    "category-recommender-1",
    "category-recommender-2",
    "category-recommender-3",
]

product_recommenders = [
    "product-recommender-1",
    "product-recommender-2",
    "product-recommender-3",
    "product-recommender-4",
    "product-recommender-5",
    "product-recommender-6",
]


# Get all available recommenders
print("Available Recommenders")
r = requests.get(f"https://api.cquotient.com/v3/personalization/recommenders/{SITE_ID}", headers=HEADERS)
for rec in r.json().get("recommenders", []):
    print(f"  - {rec.get('recommenderName', rec.get('name', rec))}")
print()


# Test category recommenders
print("Category Recommenders")
for recommender in category_recommenders:
    for cat_id, cat_name in categories:
        r = requests.post(f"{BASE}/{recommender}", headers=HEADERS, json={"categories": [{"id": cat_id}], "cookieId": "test"})
        recs = r.json().get("recs", [])
        print(f"  {recommender} | {cat_name} ({cat_id}) | {len(recs)} results")
        if recs:
            first = recs[0]
            print(f"    fields: {list(first.keys())}")
            print(f"    example: {first.get('id')} - {first.get('product_name')}")
print()


# Test product recommenders
print("Product Recommenders")
for recommender in product_recommenders:
    r = requests.post(f"{BASE}/{recommender}", headers=HEADERS, json={"products": [{"id": test_product}], "cookieId": "test"})
    recs = r.json().get("recs", [])
    print(f"  {recommender} | product={test_product} | {len(recs)} results")
    if recs:
        first = recs[0]
        print(f"    fields: {list(first.keys())}")
        print(f"    example: {first.get('id')} - {first.get('product_name')}")
print()

print("Done.")