-- ============================================================================
-- schema_migration_llm.sql
--
-- Database changes for the two LLM features.
-- Run once against your food_recall RDS database.
--
-- Feature 1: Ingredient Disambiguator
--   → disambiguation_cache table
--
-- Feature 2: Recall Explainer
--   → plain_language_summary column on recalls table
-- ============================================================================


-- 1. Disambiguation cache
--    Stores Bedrock Claude Haiku results for ambiguous ingredient tokens.
--    Keyed by SHA-256 hash of the normalised token string so the LLM is
--    called at most once per unique ambiguous ingredient, ever.
--
--    Read by:  llm_service.py → _cache_get()
--    Written:  llm_service.py → _cache_set()

CREATE TABLE IF NOT EXISTS disambiguation_cache (
    token_hash   VARCHAR(32) PRIMARY KEY,
    token        TEXT NOT NULL,
    result_json  JSONB NOT NULL,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_disambiguation_cache_created
  ON disambiguation_cache (created_at);


-- 2. Plain-language recall summary column
--    Stores the LLM-generated explanation as JSONB.
--    Structure: { headline, what_happened, what_to_do, who_is_at_risk, severity_plain }
--
--    Written by: recall_update.py → _generate_recall_summary()
--    Read by:    risk_routes.py   → _load_recall_summary()

ALTER TABLE recalls
  ADD COLUMN IF NOT EXISTS plain_language_summary JSONB;


-- 3. Verify (optional):
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'disambiguation_cache';
-- SELECT column_name, data_type FROM information_schema.columns
--   WHERE table_name = 'recalls' AND column_name = 'plain_language_summary';