-- =============================================================================
-- migration_v4_allergen_profile.sql
--
-- Adds allergen/diet profile columns to the users table.
-- Required by user_routes.py on the ingredient_diet_workflow branch.
--
-- Run once against the RDS instance:
--   psql $DATABASE_URL -f migration_v4_allergen_profile.sql
--
-- Or from EC2:
--   source ~/Capstone-Recall-Alert/backend/venv/bin/activate
--   psql -h food-recall-db.cqjm48os4obt.us-east-1.rds.amazonaws.com \
--        -U postgres -d food_recall -f migration_v4_allergen_profile.sql
-- =============================================================================

BEGIN;

-- 1. Add state column (e.g. "CA") for location-aware recall alerts
DO $$
BEGIN
    ALTER TABLE users ADD COLUMN state VARCHAR(10);
    RAISE NOTICE 'Added state column to users';
EXCEPTION
    WHEN duplicate_column THEN
        RAISE NOTICE 'state column already exists, skipping';
END $$;

-- 2. Add allergens column (TEXT[] array, e.g. {"Peanuts","Milk","Eggs"})
DO $$
BEGIN
    ALTER TABLE users ADD COLUMN allergens TEXT[] DEFAULT '{}';
    RAISE NOTICE 'Added allergens column to users';
EXCEPTION
    WHEN duplicate_column THEN
        RAISE NOTICE 'allergens column already exists, skipping';
END $$;

-- 3. Add diet_preferences column (TEXT[] array, e.g. {"Vegan","Gluten-free"})
DO $$
BEGIN
    ALTER TABLE users ADD COLUMN diet_preferences TEXT[] DEFAULT '{}';
    RAISE NOTICE 'Added diet_preferences column to users';
EXCEPTION
    WHEN duplicate_column THEN
        RAISE NOTICE 'diet_preferences column already exists, skipping';
END $$;

COMMIT;

-- Verify:
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'users' AND column_name IN ('state', 'allergens', 'diet_preferences');
