"""
llm_service.py – LLM-powered features via AWS Bedrock (Claude Haiku).

Two features, one module, one Bedrock client:

  
    FEATURE 1: INGREDIENT DISAMBIGUATOR                            
                                                                   
    Problem:  "natural flavors", "modified food starch", "spices"  
              — the deterministic synonym DB can't classify these.  
                                                                   
    Solution: After the 3-pass deterministic detection, identify    
              unresolved tokens → batch into a single Bedrock call  
              → merge results back as AllergenMatch / advisory      
              objects the existing engine already understands.       
                                                                   
    Called from: ingredient_risk_engine.py → analyse_product_risk() 
    Endpoint:   GET /api/risk/scan/{upc}?enable_ai=true            
    Cache:      disambiguation_cache table (30-day TTL)             
    Fallback:   if Bedrock is down → deterministic-only (graceful)  
  ─────────────────────────────────────────────────────────────────
    FEATURE 2: RECALL EXPLAINER                                    
                                                                   
    Problem:  FDA enforcement text is dense legalese. Users need    
              "what happened / what to do / who's at risk".         
                                                                   
    Solution: One Bedrock call per recall. Result stored in the     
              recalls table (plain_language_summary JSONB column).  
              Generated once during recall refresh, never repeated. 
                                                                   
    Called from: recall_update.py → run_recall_refresh()            
    Returned in: risk_routes.py → /api/risk/scan/{upc}             
    Fallback:   if Bedrock is down → raw FDA text (always present)  
  ─────────────────────────────────────────────────────────────────

AWS Bedrock setup:
  - Model: Claude Haiku (us.anthropic.claude-haiku-4-5-20251001)
  - Auth:  IAM role on EC2 instance (same as Textract — no API key needed)
  - Region: us-east-1 (matches your RDS and Textract setup)

To enable on a new EC2 instance, add this to the IAM role policy:
  {
    "Effect": "Allow",
    "Action": "bedrock:InvokeModel",
    "Resource": "arn:aws:bedrock:us-east-1::foundation-model/us.anthropic.claude-haiku-4-5-20251001"
  }
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, asdict
from typing import Optional

import boto3
from botocore.exceptions import ClientError

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
#  1. BEDROCK CLIENT
# ═══════════════════════════════════════════════════════════════════════════════
#
#  Single shared client for both features. Initialized lazily on first call
#  so the app starts even if Bedrock permissions aren't configured yet.

_bedrock_client = None

BEDROCK_MODEL_ID = os.getenv(
    "BEDROCK_MODEL_ID",
    "us.anthropic.claude-haiku-4-5-20251001-v1:0",
)
BEDROCK_REGION = os.getenv("BEDROCK_REGION", "us-east-1")


def _get_bedrock_client():
    """Lazy-init the Bedrock Runtime client."""
    global _bedrock_client
    if _bedrock_client is None:
        _bedrock_client = boto3.client(
            "bedrock-runtime",
            region_name=BEDROCK_REGION,
        )
    return _bedrock_client


def _invoke_bedrock(system_prompt: str, user_prompt: str, max_tokens: int = 1024) -> Optional[str]:
    """
    Send a prompt to Bedrock and return the text response.
    Returns None on any failure (timeout, permissions, throttle, etc.).
    """
    try:
        client = _get_bedrock_client()
        response = client.invoke_model(
            modelId=BEDROCK_MODEL_ID,
            contentType="application/json",
            accept="application/json",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": [{"role": "user", "content": user_prompt}],
            }),
        )
        body = json.loads(response["body"].read())
        # Extract text from content blocks
        text = ""
        for block in body.get("content", []):
            if block.get("type") == "text":
                text += block.get("text", "")
        return text.strip() if text else None

    except ClientError as exc:
        error_code = exc.response["Error"]["Code"]
        log.warning("Bedrock API error (%s): %s", error_code, exc)
        return None
    except Exception as exc:
        log.warning("Bedrock call failed: %s", exc)
        return None


def _parse_json_response(raw: str) -> Optional[list | dict]:
    """Safely parse LLM JSON output, stripping markdown fences if present."""
    if not raw:
        return None
    cleaned = raw.strip()
    cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        log.warning("Failed to parse LLM JSON: %s — raw: %s", exc, raw[:200])
        return None


# ═══════════════════════════════════════════════════════════════════════════════
#  2. INGREDIENT DISAMBIGUATOR
# ═══════════════════════════════════════════════════════════════════════════════

# ── 2a. Known ambiguous ingredients ──────────────────────────────────────────
#
# These are structurally ambiguous — their allergen/diet status depends on
# manufacturing details not on the label. The deterministic engine can't
# resolve them. The LLM uses context clues from surrounding ingredients.

KNOWN_AMBIGUOUS: dict[str, str] = {
    "natural flavors":        "Could be derived from any plant or animal source",
    "natural flavor":         "Could be derived from any plant or animal source",
    "artificial flavors":     "Usually synthetic, may contain allergen-derived carriers",
    "artificial flavor":      "Usually synthetic, may contain allergen-derived carriers",
    "natural and artificial flavors": "Mixed source — unknown derivation",
    "flavoring":              "Unspecified source",
    "flavourings":            "Unspecified source",
    "spices":                 "May contain mustard, celery, sesame, or other allergens",
    "spice":                  "May contain mustard, celery, sesame, or other allergens",
    "spice extractives":      "May contain mustard, celery, sesame, or other allergens",
    "seasoning":              "May contain undisclosed allergens",
    "modified food starch":   "Usually corn, but can be wheat-derived",
    "modified starch":        "Usually corn, but can be wheat-derived",
    "food starch":            "Usually corn, but can be wheat-derived",
    "starch":                 "Source grain unspecified",
    "dextrin":                "Usually corn, can be wheat",
    "lecithin":               "Could be soy or sunflower",
    "mono and diglycerides":  "Can be plant or animal-derived",
    "mono- and diglycerides": "Can be plant or animal-derived",
    "diglycerides":           "Can be plant or animal-derived",
    "monoglycerides":         "Can be plant or animal-derived",
    "glycerin":               "Can be plant or animal-derived",
    "glycerine":              "Can be plant or animal-derived",
    "glycerol":               "Can be plant or animal-derived",
    "vitamin d3":             "Usually from lanolin (animal); sometimes from lichen (vegan)",
    "cholecalciferol":        "Vitamin D3 — usually from lanolin (animal)",
    "vitamin d":              "D2 is plant-based, D3 is usually animal-derived",
    "confectioner's glaze":   "Shellac — derived from lac insect secretions",
    "confectioners glaze":    "Shellac — derived from lac insect secretions",
    "enzyme":                 "Can be microbial, plant, or animal-derived",
    "enzymes":                "Can be microbial, plant, or animal-derived",
    "rennet":                 "Animal rennet vs microbial rennet unknown",
    "lipase":                 "Can be animal or microbial",
    "pepsin":                 "Usually animal-derived (porcine)",
    "l-cysteine":             "Often derived from human hair or duck feathers",
    "natural color":          "Source varies — could be carmine (insect) or plant",
    "natural colours":        "Source varies — could be carmine (insect) or plant",
    "caramel color":          "Usually vegan, but production process may use dairy",
    "color added":            "Source unspecified",
}

# Ingredients that are obviously benign — never send to LLM.
_BENIGN: frozenset = frozenset({
    "water", "purified water", "filtered water", "spring water",
    "salt", "sea salt", "kosher salt", "iodized salt",
    "sugar", "cane sugar", "brown sugar", "powdered sugar",
    "oil", "olive oil", "canola oil", "palm oil", "coconut oil",
    "vinegar", "white vinegar", "apple cider vinegar",
    "baking soda", "baking powder", "sodium bicarbonate",
    "citric acid", "ascorbic acid", "lactic acid",
    "potassium sorbate", "calcium chloride", "sodium chloride",
    "pectin", "agar", "xanthan gum", "guar gum", "cellulose gum",
    "yeast", "vanilla", "vanilla extract", "cocoa", "cocoa powder",
    "cocoa butter", "iron", "zinc", "calcium", "niacin", "riboflavin",
    "thiamine mononitrate", "folic acid", "reduced iron", "ferrous sulfate",
    "annatto", "beta carotene", "turmeric", "paprika",
    "black pepper", "garlic", "onion", "cinnamon",
    "lemon juice", "lime juice", "tomato paste",
    "rice", "rice flour", "corn flour", "cornstarch", "corn starch",
    "tapioca starch", "potato starch", "carbon dioxide",
})


# ── 2b. Cache layer ─────────────────────────────────────────────────────────
#
# Results are cached per-token so the LLM is called at most once per unique
# ambiguous ingredient, ever, across all users. In-memory dict is the
# fallback when the DB isn't available (tests, local dev).

_memory_cache: dict[str, dict] = {}


def _cache_key(token: str) -> str:
    return hashlib.sha256(token.strip().lower().encode()).hexdigest()[:32]


def _cache_get(token: str) -> Optional[dict]:
    """
    Read from disambiguation_cache table, fallback to memory.

    DB schema (see schema_migration_llm.sql):
      disambiguation_cache(token_hash PK, token, result_json JSONB, created_at)
    """
    key = _cache_key(token)
    try:
        from database import execute_query
        rows = execute_query(
            """SELECT result_json FROM disambiguation_cache
               WHERE token_hash = %s AND created_at > NOW() - INTERVAL '30 days'
               LIMIT 1;""",
            (key,),
        )
        if rows and rows[0].get("result_json"):
            result = rows[0]["result_json"]
            return result if isinstance(result, dict) else json.loads(result)
    except Exception:
        pass
    return _memory_cache.get(key)


def _cache_set(token: str, result: dict) -> None:
    """Write to disambiguation_cache table + memory."""
    key = _cache_key(token)
    try:
        from database import execute_query
        execute_query(
            """INSERT INTO disambiguation_cache (token_hash, token, result_json)
               VALUES (%s, %s, %s)
               ON CONFLICT (token_hash) DO UPDATE
               SET result_json = EXCLUDED.result_json, created_at = NOW();""",
            (key, token.strip().lower(), json.dumps(result)),
        )
    except Exception:
        pass
    _memory_cache[key] = result


# ── 2c. Token identification ─────────────────────────────────────────────────

def identify_ambiguous_tokens(
    parsed_tokens: list[str],
    user_allergens: list[str],
    user_diets: list[str],
    allergen_synonyms: dict[str, set[str]],
    diet_rules: dict[str, dict],
) -> list[str]:
    """
    Find tokens the deterministic engine couldn't resolve.

    A token is ambiguous if:
      1. It's in KNOWN_AMBIGUOUS, OR
      2. It's ≥4 chars, not in any synonym set, and not in the benign list

    Only runs if the user actually has allergens/diets configured.
    """
    if not user_allergens and not user_diets:
        return []

    all_known: set[str] = set()
    for syns in allergen_synonyms.values():
        all_known.update(syns)
    for rules in diet_rules.values():
        all_known.update(rules.get("forbidden", set()))

    result: list[str] = []
    seen: set[str] = set()
    for token in parsed_tokens:
        if token in seen:
            continue
        if token in KNOWN_AMBIGUOUS:
            seen.add(token)
            result.append(token)
        elif len(token) >= 4 and token not in all_known and token not in _BENIGN:
            seen.add(token)
            result.append(token)
    return result


# ── 2d. LLM prompt + call ───────────────────────────────────────────────────

_DISAMBIG_SYSTEM = """\
You are a food safety ingredient analysis system. Assess ambiguous food \
ingredients for allergen content and dietary compatibility.

RULES:
- Return ONLY valid JSON array. No markdown, no backticks, no explanation.
- Be conservative: when unsure, say "UNKNOWN".
- Never hallucinate allergen associations.
- Use the full ingredient context to make inferences.

Each element must have exactly these fields:
{
  "token": "the ingredient token",
  "likely_allergens": ["Milk"],
  "allergen_confidence": "HIGH|MEDIUM|LOW|UNKNOWN",
  "diet_incompatible": ["Vegan"],
  "diet_confidence": "HIGH|MEDIUM|LOW|UNKNOWN",
  "is_animal_derived": true|false|null,
  "reasoning": "1-sentence explanation"
}

Canonical allergen names: Milk, Eggs, Peanuts, Tree Nuts, Fish, Shellfish, \
Wheat, Soy, Sesame, Gluten, Sulfites, Mustard, Celery, Lupin, Corn.
Diet names: Vegan, Vegetarian, Gluten-Free, Dairy-Free, Keto, Paleo, Halal, Kosher.\
"""


def _build_disambig_prompt(
    ambiguous_tokens: list[str],
    full_ingredients: str,
    user_allergens: list[str],
    user_diets: list[str],
) -> str:
    token_lines = []
    for token in ambiguous_tokens:
        reason = KNOWN_AMBIGUOUS.get(token, "Not in known ingredient database")
        token_lines.append(f'  - "{token}" — {reason}')

    return (
        f"AMBIGUOUS INGREDIENTS:\n"
        f"{chr(10).join(token_lines)}\n\n"
        f"FULL INGREDIENT LIST (for context):\n  {full_ingredients}\n\n"
        f"USER ALLERGENS: {', '.join(user_allergens) or 'None'}\n"
        f"USER DIETS: {', '.join(user_diets) or 'None'}\n\n"
        f"Return a JSON array with one object per ambiguous ingredient."
    )


@dataclass
class DisambiguationResult:
    token:                str
    likely_allergens:     list[str]
    allergen_confidence:  str
    diet_incompatible:    list[str]
    diet_confidence:      str
    is_animal_derived:    Optional[bool]
    reasoning:            str

    def to_dict(self) -> dict:
        return asdict(self)


def disambiguate_ingredients(
    parsed_tokens: list[str],
    full_ingredients_text: str,
    user_allergens: list[str],
    user_diets: list[str],
    allergen_synonyms: dict,
    diet_rules: dict,
) -> list[DisambiguationResult]:
    """
    ┌────────────────────────────────────────────────────────────────┐
    │  MAIN ENTRY POINT — called from analyse_product_risk()         │
    │                                                                │
    │  Pipeline:                                                     │
    │    1. identify_ambiguous_tokens()                               │
    │    2. Check disambiguation_cache for each                      │
    │    3. Batch cache misses into single Bedrock call               │
    │    4. Cache each result (per-token, 30-day TTL)                │
    │    5. Return list of DisambiguationResult                      │
    │                                                                │
    │  Returns [] on any failure — engine falls back to deterministic │
    └────────────────────────────────────────────────────────────────┘
    """
    ambiguous = identify_ambiguous_tokens(
        parsed_tokens, user_allergens, user_diets,
        allergen_synonyms, diet_rules,
    )
    if not ambiguous:
        return []

    # Check cache
    results: list[DisambiguationResult] = []
    uncached: list[str] = []
    for token in ambiguous:
        cached = _cache_get(token)
        if cached:
            try:
                results.append(DisambiguationResult(**cached))
            except Exception:
                uncached.append(token)
        else:
            uncached.append(token)

    # Call Bedrock for cache misses
    if uncached:
        prompt = _build_disambig_prompt(
            uncached, full_ingredients_text, user_allergens, user_diets,
        )
        raw = _invoke_bedrock(_DISAMBIG_SYSTEM, prompt, max_tokens=1024)
        parsed = _parse_json_response(raw)

        if isinstance(parsed, list):
            for item in parsed:
                try:
                    dr = DisambiguationResult(
                        token=str(item.get("token", "")),
                        likely_allergens=item.get("likely_allergens") or [],
                        allergen_confidence=str(item.get("allergen_confidence", "UNKNOWN")).upper(),
                        diet_incompatible=item.get("diet_incompatible") or [],
                        diet_confidence=str(item.get("diet_confidence", "UNKNOWN")).upper(),
                        is_animal_derived=item.get("is_animal_derived"),
                        reasoning=str(item.get("reasoning", "")),
                    )
                    _cache_set(dr.token, dr.to_dict())
                    results.append(dr)
                except Exception as exc:
                    log.warning("Failed to parse disambiguation item: %s", exc)
        else:
            log.warning("Bedrock returned no parseable results for %d tokens.", len(uncached))

    return results


# ═══════════════════════════════════════════════════════════════════════════════
#  3. RECALL EXPLAINER
# ═══════════════════════════════════════════════════════════════════════════════

_RECALL_SYSTEM = """\
You are a consumer food safety communicator. Convert FDA recall enforcement \
text into a clear, plain-language summary that a grocery shopper can \
understand in 5 seconds.

RULES:
- Return ONLY valid JSON object. No markdown, no backticks.
- Write at a 6th-grade reading level.
- Be direct and actionable.
- Never downplay severity.

Return exactly this JSON structure:
{
  "headline": "2-5 word summary (e.g. 'Possible Listeria contamination')",
  "what_happened": "1-2 sentences: what is wrong with this product",
  "what_to_do": "1-2 sentences: specific action the consumer should take",
  "who_is_at_risk": "1 sentence: who should be especially careful",
  "severity_plain": "1 sentence explaining the recall class in plain language"
}\
"""


@dataclass
class RecallExplanation:
    headline:       str
    what_happened:  str
    what_to_do:     str
    who_is_at_risk: str
    severity_plain: str

    def to_dict(self) -> dict:
        return asdict(self)


def explain_recall(
    product_name: str,
    reason: str,
    severity: str,
    firm_name: str = "",
    distribution: str = "",
) -> Optional[RecallExplanation]:
    """
    ┌────────────────────────────────────────────────────────────────┐
    │  Generate a plain-language recall explanation.                  │
    │                                                                │
    │  Called from: recall_update.py → run_recall_refresh()           │
    │  Result stored in: recalls.plain_language_summary (JSONB)      │
    │  Returned in: risk_routes.py → /scan/{upc} response            │
    │                                                                │
    │  Returns None on failure — raw FDA text is always available.   │
    └────────────────────────────────────────────────────────────────┘
    """
    if not reason:
        return None

    prompt = (
        f"Product: {product_name}\n"
        f"Recalling firm: {firm_name}\n"
        f"FDA reason: {reason}\n"
        f"Classification: {severity}\n"
        f"Distribution: {distribution}\n\n"
        f"Generate the plain-language summary JSON."
    )

    raw = _invoke_bedrock(_RECALL_SYSTEM, prompt, max_tokens=512)
    parsed = _parse_json_response(raw)

    if isinstance(parsed, dict):
        try:
            return RecallExplanation(
                headline=str(parsed.get("headline", "")),
                what_happened=str(parsed.get("what_happened", "")),
                what_to_do=str(parsed.get("what_to_do", "")),
                who_is_at_risk=str(parsed.get("who_is_at_risk", "")),
                severity_plain=str(parsed.get("severity_plain", "")),
            )
        except Exception as exc:
            log.warning("Failed to parse recall explanation: %s", exc)

    return None