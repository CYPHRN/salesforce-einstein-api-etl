import requests
import pyodbc
import time
import argparse
from datetime import datetime

# CONFIG — UPDATE THESE
API_KEY = "YOUR-API-KEY"
SITE_ID = "YOUR-SITE-ID"
BASE = f"https://api.cquotient.com/v3/personalization/recs/{SITE_ID}"
HEADERS = {"x-cq-client-id": API_KEY}

DELAY = 1  # seconds between API calls

# AZURE Active Directory Connection
SQL_CONN = (
    "DRIVER={ODBC Driver 17 for SQL Server};"
    "SERVER=YOUR-SERVER.database.windows.net;"
    "DATABASE=YOUR-DATABASE;"
    "Authentication=ActiveDirectoryIntegrated;"
    "Encrypt=yes;TrustServerCertificate=no;Connection Timeout=30;"
)

MASTER_DB = "[YOUR-MASTER-DB]"

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

# HELPERS

def call_api(recommender, params):
    try:
        r = requests.get(f"{BASE}/{recommender}", headers=HEADERS, params=params, timeout=60)
        if r.status_code == 200:
            return r.json().get("recs", [])
        else:
            print(f"  WARNING: HTTP {r.status_code} for {recommender} {params}")
            return []
    except Exception as e:
        print(f"  ERROR: {recommender} {params} — {e}")
        return []

# CATEGORY MODE

def run_category(conn):
    cursor = conn.cursor()
    cursor.execute(f"SELECT CATEGORY_ID, CATEGORY_DESC FROM {MASTER_DB}.[MASTER].SFCC_RECOM_CATEGORY")
    categories = [(str(r.CATEGORY_ID), r.CATEGORY_DESC) for r in cursor.fetchall()]
    cursor.close()
    print(f"Loaded {len(categories)} categories")

    now = datetime.now()

    for recommender in category_recommenders:
        print(f"\n--- {recommender} ---")

        cursor = conn.cursor()
        cursor.execute("DELETE FROM SRC_SFCC.RECOMMENDER_CATEGORY WHERE recommender = ?", recommender)
        conn.commit()
        print(f"  Deleted old SRC rows for '{recommender}'")

        rows = []
        for cat_id, cat_desc in categories:
            recs = call_api(recommender, {"categoryId": cat_id})
            print(f"  {cat_desc} ({cat_id}) — {len(recs)} recs")

            for rec in recs:
                rows.append((
                    recommender, cat_id, cat_desc,
                    rec.get("id"), rec.get("product_name"),
                    rec.get("image_url"), rec.get("product_url"),
                    now
                ))
            time.sleep(DELAY)

        if rows:
            cursor.executemany("""
                INSERT INTO SRC_SFCC.RECOMMENDER_CATEGORY
                    (recommender, category_id, category_desc, product_id_recom,
                     product_name, image_url, product_url, timestamp)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, rows)
            conn.commit()
            print(f"  Inserted {len(rows)} rows into SRC")

        cursor.execute("""
            INSERT INTO HST_SFCC.RECOMMENDER_CATEGORY
                (recommender, category_id, category_desc, product_id_recom,
                 product_name, image_url, product_url, timestamp)
            SELECT recommender, category_id, category_desc, product_id_recom,
                   product_name, image_url, product_url, timestamp
            FROM SRC_SFCC.RECOMMENDER_CATEGORY
            WHERE recommender = ?
        """, recommender)
        conn.commit()
        print(f"  Copied to HST")
        cursor.close()

# PRODUCT MODE

def run_product(conn, recommender):
    cursor = conn.cursor()
    cursor.execute(f"SELECT ARTICLE_CODE FROM {MASTER_DB}.[MASTER].SFCC_RECOM_PRODUCTS")
    products = [str(r.ARTICLE_CODE).strip() for r in cursor.fetchall()]
    cursor.close()
    print(f"Loaded {len(products)} products")

    if not products:
        print("ERROR: No products in master table.")
        return

    print(f"\n--- {recommender} ---")
    now = datetime.now()

    cursor = conn.cursor()
    cursor.execute("DELETE FROM SRC_SFCC.RECOMMENDER_PRODUCT WHERE recommender = ?", recommender)
    conn.commit()
    cursor.close()
    print(f"  Deleted old SRC rows for '{recommender}'")

    batch = []
    total_inserted = 0
    for i, article_code in enumerate(products, 1):
        recs = call_api(recommender, {"products": article_code})

        for rec in recs:
            batch.append((
                recommender, article_code,
                rec.get("id"), rec.get("product_name"),
                rec.get("image_url"), rec.get("product_url"),
                now
            ))

        if i % 100 == 0 or i == len(products):
            if batch:
                cursor = conn.cursor()
                cursor.executemany("""
                    INSERT INTO SRC_SFCC.RECOMMENDER_PRODUCT
                        (recommender, product_id, product_id_recom,
                         product_name, image_url, product_url, timestamp)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, batch)
                conn.commit()
                cursor.close()
                total_inserted += len(batch)
                batch = []
            print(f"  Progress: {i}/{len(products)} products done — {total_inserted} rows in SRC so far")

        time.sleep(DELAY)

    print(f"  Total inserted: {total_inserted} rows into SRC")

    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO HST_SFCC.RECOMMENDER_PRODUCT
            (recommender, product_id, product_id_recom,
             product_name, image_url, product_url, timestamp)
        SELECT recommender, product_id, product_id_recom,
               product_name, image_url, product_url, timestamp
        FROM SRC_SFCC.RECOMMENDER_PRODUCT
        WHERE recommender = ?
    """, recommender)
    conn.commit()
    print(f"  Copied {cursor.rowcount} rows to HST")
    cursor.close()

# MAIN

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", required=True, choices=["category", "product"])
    parser.add_argument("--recommender", required=False)
    args = parser.parse_args()

    if args.mode == "product" and not args.recommender:
        print("ERROR: --recommender is required for product mode")
        exit(1)

    if args.mode == "product" and args.recommender not in product_recommenders:
        print(f"ERROR: unknown recommender '{args.recommender}'")
        exit(1)

    print(f"Starting ETL — mode={args.mode}, recommender={args.recommender or 'ALL CATEGORY'}")
    print(f"Time: {datetime.now()}")
    print()

    conn = pyodbc.connect(SQL_CONN)
    print("Connected to database")

    if args.mode == "category":
        run_category(conn)
    else:
        run_product(conn, args.recommender)

    conn.close()
    print(f"\nDone. {datetime.now()}")