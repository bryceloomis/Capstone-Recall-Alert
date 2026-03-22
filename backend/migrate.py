from database import execute_query

migrations = [
    "ALTER TABLE recalls ADD COLUMN IF NOT EXISTS firm_name VARCHAR(200);",
    "ALTER TABLE recalls ADD COLUMN IF NOT EXISTS distribution_pattern VARCHAR(500);",
    "ALTER TABLE recalls ALTER COLUMN upc TYPE VARCHAR(50);",
    "ALTER TABLE recalls DROP CONSTRAINT recalls_upc_date_unique;",
    "ALTER TABLE recalls ADD CONSTRAINT recalls_product_brand_unique UNIQUE (upc, product_name, brand_name);",
    "ALTER TABLE alerts RENAME COLUMN sent_at TO created_at;",
    "ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);",
]

for sql in migrations:
    try:
        execute_query(sql)
        print(f"OK: {sql[:70]}")
    except Exception as e:
        print(f"SKIP: {sql[:70]}\n  -> {e}")

print("\nDone.")
