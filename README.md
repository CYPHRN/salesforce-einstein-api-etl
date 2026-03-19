# SFCC Einstein API - Product Recommendations ETL

Pulls product recommendation data from the Salesforce Commerce Cloud (SFCC) Einstein API and stores it in a SQL Server data warehouse.

## What it does

- Calls the Einstein Recommendations API for a list of categories and products
- Stores the results in SRC tables (latest data) and HST tables (historical)
- Runs on a weekly schedule via SQL Agent jobs, one recommender per day

## Scripts

### 01_test_einstein_api.py

Quick test script to validate the API works before setting anything up.

- Lists all available recommenders for your site
- Tests category recommenders against a few sample categories
- Tests product recommenders against a sample product ID
- Prints the response fields so you know what the API returns
- No database connection needed, just `pip install requests`

How to run:

```
python 01_test_einstein_api.py
```

What to fill in:

- `API_KEY` - your Einstein API key (from Postman export or Einstein Configurator)
- `SITE_ID` - your SFCC site ID
- `categories` - a few category IDs from your webshop to test with
- `test_product` - a product ID from your catalog

### 02_einstein_etl.py

The actual ETL script. Calls the API, parses the response, writes to the database.

- Two modes: `category` (runs all category recommenders in one go) and `product` (runs one product recommender per execution)
- Reads the list of categories/products from master tables in the database
- For each category or product: calls the API, waits 1 second, moves to the next
- Product mode inserts in batches of 100 so data is saved even if the process is interrupted
- Per recommender: deletes old rows from SRC, inserts new ones, then copies to HST
- Connects using Azure AD Integrated auth (no credentials in the script)

How to run:

```
# all category recommenders
python 02_einstein_etl.py --mode category

# one product recommender
python 02_einstein_etl.py --mode product --recommender cart-and-wishlist
```

What to fill in:

- `API_KEY` - your Einstein API key
- `SITE_ID` - your SFCC site ID
- `SQL_CONN` - your database connection string (server, database name)
- `MASTER_DB` - database name where your category and product master tables live
- `category_recommenders` - list of your category recommender names
- `product_recommenders` - list of your product recommender names

## Requirements

- Python 3.x
- `pip install requests pyodbc`
- ODBC Driver 17 for SQL Server
- Azure AD access to the target database (for script 02)

## Database tables

The ETL writes to 4 tables (created separately via SQL setup script):

- `SRC_SFCC.RECOMMENDER_CATEGORY` - latest category recommendations
- `SRC_SFCC.RECOMMENDER_PRODUCT` - latest product recommendations
- `HST_SFCC.RECOMMENDER_CATEGORY` - historical category recommendations
- `HST_SFCC.RECOMMENDER_PRODUCT` - historical product recommendations

And reads from 2 master tables (maintained separately):

- `MASTER.SFCC_RECOM_CATEGORY` - list of category IDs to loop over
- `MASTER.SFCC_RECOM_PRODUCTS` - list of product IDs (article codes) to loop over

## Schedule

Designed to run via SQL Agent jobs at 01:00 AM:

- Sunday: all category recommenders (~2 min)
- Monday to Saturday: one product recommender per day (~38 min each)

1 second delay between API calls. No published rate limit on the Einstein API but this keeps it safe and avoids affecting recommendation results.
