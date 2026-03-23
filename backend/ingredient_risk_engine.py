"""
ingredient_risk_engine.py – Deterministic ingredient risk scoring engine.
 
Provides three independent risk assessments on a per-product basis:
 
  1. ALLERGEN DETECTION
     Maps the user's declared allergens against the product ingredient list
     using a comprehensive synonym database covering the FDA "Big 9" allergens
     plus several extended categories.  Each allergen match carries a
     confidence score (DEFINITE / PROBABLE) based on how it was matched:
       DEFINITE  — exact token hit or whole-word compound match
       PROBABLE  — substring derivative match OR advisory "may contain" phrase
     Both DEFINITE and PROBABLE trigger a hard stop (DONT_BUY).
 
  2. DIET INCOMPATIBILITY
     Evaluates the ingredient list against rule sets for common dietary
     patterns (Vegan, Vegetarian, Gluten-Free, Kosher, Halal, Keto,
     Dairy-Free, Paleo).  Each flagged ingredient specifies *why* it is
     incompatible and its confidence level.
 
  3. TWO-LAYER VERDICT SYSTEM
 
     Layer 1 — HARD STOPS (binary gates, evaluated first):
       Gate 1: RECALL      — active FDA recall
       Gate 2: ALLERGEN    — DEFINITE or PROBABLE allergen match
                             (includes advisory "may contain" language)
       Gate 3: DIET_STRICT — DEFINITE violation of a strict diet
                             (Vegan, Vegetarian, Gluten-Free, Dairy-Free,
                              Halal, Kosher — NOT Keto or Paleo)
       Any gate firing → DONT_BUY immediately, Layer 2 skipped.
 
     Layer 2 — SOFT CAUTION SIGNALS (only when no hard stop fired):
       ADDITIVE       — any single flagged additive → CAUTION immediately,
                        no point accumulation required.
                        is_safety_risk=False so frontend renders a softer badge.
       DIET_SOFT      — PROBABLE diet flag or DEFINITE on non-strict diet
                        (Keto/Paleo). Point-based: 4–5 pts each.
                        is_safety_risk=False — preference conflict, not medical.
       LOW_CONFIDENCE — missing or very short ingredient list. Point-based:
                        8–12 pts. is_safety_risk=True — unknown = conservative.
       CROSS_CONTACT  — reserved for POSSIBLE-confidence allergen matches
                        (not currently assigned by deterministic engine).
                        is_safety_risk=True.
 
     Verdict rule:
       any ADDITIVE signal present                    → CAUTION
       no ADDITIVE but non-additive score ≥ threshold → CAUTION
       otherwise                                      → OK
 
All matching is deterministic — no ML model required.  Accuracy comes from
the breadth of the synonym dictionaries, the multi-pass parsing strategy,
and the compound exclusion dicts that prevent plant-based false positives.
 
Confidence levels:
  DEFINITE — exact token in synonym set, or whole-word match in compound
             ("gelatin" as a whole word in "beef gelatin")
  PROBABLE — substring derivative match ("sodium caseinate" contains "casein"),
             OR advisory phrase match ("May Contain Peanuts")
             Both levels trigger the ALLERGEN hard stop → DONT_BUY.
  POSSIBLE — (reserved; not currently assigned — kept for future use)
 
Design principle: Recall > Precision.
  A false negative (missed allergen) is always more dangerous than a
  false positive (extra caution). The engine errs toward warning.
 
Usage:
    from ingredient_risk_engine import (
        analyse_product_risk,
        detect_allergens,
        check_diet_compatibility,
    )
 
    result = analyse_product_risk(
        ingredients_text="water, wheat flour, milk, soy lecithin",
        user_allergens=["Milk", "Soy"],
        user_diets=["Vegan", "Gluten-Free"],
        is_recalled=False,
    )
"""
 
from __future__ import annotations
 
import re
import logging
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Optional
 
try:
    from LLM_services import disambiguate_ingredients, DisambiguationResult, explain_recall as _llm_available
    _LLM_AVAILABLE = True
except Exception:
    _LLM_AVAILABLE = False
    DisambiguationResult = None  # type: ignore
 
log = logging.getLogger(__name__)
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# 1.  CONSTANTS & ENUMS
# ═══════════════════════════════════════════════════════════════════════════════
 
class Confidence(str, Enum):
    DEFINITE = "DEFINITE"    # exact or whole-word compound match
    PROBABLE = "PROBABLE"    # substring derivative OR "may contain" advisory
    POSSIBLE = "POSSIBLE"    # reserved — not currently assigned
 
 
class Severity(str, Enum):
    HIGH   = "HIGH"          # life-threatening potential (anaphylaxis allergens)
    MEDIUM = "MEDIUM"        # significant but rarely life-threatening
    LOW    = "LOW"           # mild intolerance or preference-based
 
 
# Allergens that commonly cause anaphylaxis → HIGH severity by default.
_HIGH_SEVERITY_ALLERGENS = frozenset({
    "Milk", "Eggs", "Peanuts", "Tree Nuts", "Fish",
    "Shellfish", "Wheat", "Soy", "Sesame",
})
 
# ── Compound exclusions ────────────────────────────────────────────────────────
# Pass 2 substring matching creates false positives when a short synonym word
# appears inside a compound ingredient that is NOT the allergen/violation.
#
# Examples:
#   "cocoa butter"  — "butter" is a Milk synonym but cocoa butter is plant fat.
#   "peanut butter" — "butter" is a Milk synonym but peanut butter has no dairy.
#   "oat milk"      — "milk" is a Milk synonym but oat milk is plant-based.
#
# Structure: { synonym_or_forbidden_word : frozenset of full compound tokens
#              where that word is benign and should NOT match }
#
# Maintained separately for allergen vs diet because the same compound can be
# safe for one check but not the other:
#   "peanut butter" — NOT dairy (excluded from ALLERGEN Milk check)
#                   — BUT must still fire for the Peanut allergen check
#                   — AND IS vegan (excluded from DIET Vegan check)
 
ALLERGEN_COMPOUND_EXCLUSIONS: dict[str, frozenset] = {
    # "butter" tokens that are plant-derived fats, not dairy
    "butter": frozenset({
        "cocoa butter",       "coconut butter",    "shea butter",
        "mango butter",       "kokum butter",      "illipe butter",
        "peanut butter",      "almond butter",     "cashew butter",
        "sunflower butter",   "hazelnut butter",   "walnut butter",
        "pecan butter",       "pistachio butter",  "macadamia butter",
        "apple butter",       "pumpkin butter",
    }),
    # "milk" tokens that are plant-based, not dairy
    "milk": frozenset({
        "oat milk",      "almond milk",    "soy milk",       "coconut milk",
        "rice milk",     "cashew milk",    "hemp milk",      "flax milk",
        "pea milk",      "macadamia milk", "pistachio milk", "hazelnut milk",
        "potato milk",   "banana milk",    "walnut milk",
    }),
    # "cream" — plant-based only
    "cream": frozenset({
        "coconut cream", "oat cream", "cashew cream", "almond cream",
    }),
    # "wheat" — ingredients whose names contain "wheat" but are NOT wheat-derived
    # "buckwheat" is a seed (Polygonaceae family), unrelated to wheat despite the name.
    # "wheatgrass juice powder" is sometimes used in products but IS wheat — intentionally
    # excluded from this list so it continues to fire correctly.
    "wheat": frozenset({
        "buckwheat",           # pseudocereal — not wheat, naturally gluten-free
        "buckwheat flour",     # same
        "buckwheat groats",    # same
        "buckwheat flakes",    # same
        "buckwheat noodles",   # soba noodles — often pure buckwheat
    }),
    # "flour" — non-wheat flours that match the Wheat synonym "flour" via substring
    # These are safe for Wheat allergy (they are nut/seed/root-derived, not wheat).
    # Note: Rice flour IS blocked for Gluten-Free diet users (by design — the GF
    # forbidden set contains "flour" to catch all unqualified flour references and
    # relies on the label to say "rice flour" explicitly when it is GF-safe).
    "flour": frozenset({
        "almond flour",      # tree nut — not wheat
        "coconut flour",     # coconut — not wheat
        "rice flour",        # rice — not wheat (but not GF-certified by default)
        "oat flour",         # oats — not wheat (but may contain gluten)
        "chickpea flour",    # legume — not wheat
        "tapioca flour",     # cassava — not wheat
        "cassava flour",     # cassava — not wheat
        "potato flour",      # potato — not wheat
        "corn flour",        # corn — not wheat
        "soy flour",         # soy — not wheat
        "buckwheat flour",   # buckwheat — not wheat despite name (gluten-free grain)
        "teff flour",        # teff — not wheat
        "sorghum flour",     # sorghum — not wheat
        "quinoa flour",      # quinoa — not wheat
        "hemp flour",        # hemp — not wheat
        "flaxseed flour",    # flax — not wheat
        "sunflower flour",   # sunflower seed — not wheat
        "hazelnut flour",    # hazelnut — not wheat
        "chestnut flour",    # chestnut — not wheat
        "tiger nut flour",   # tiger nut — not wheat
    }),
}
 
DIET_COMPOUND_EXCLUSIONS: dict[str, frozenset] = {
    # "butter" in Vegan/Dairy-Free forbidden sets — plant butters are fine
    "butter": frozenset({
        "cocoa butter",       "coconut butter",    "shea butter",
        "mango butter",       "peanut butter",     "almond butter",
        "cashew butter",      "sunflower butter",  "hazelnut butter",
        "walnut butter",      "pecan butter",      "pistachio butter",
        "macadamia butter",   "apple butter",      "pumpkin butter",
    }),
    # "milk" tokens that are plant-based — NOT dairy, ARE vegan/dairy-free
    "milk": frozenset({
        "oat milk",      "almond milk",    "soy milk",       "coconut milk",
        "rice milk",     "cashew milk",    "hemp milk",      "flax milk",
        "pea milk",      "macadamia milk", "pistachio milk", "hazelnut milk",
        "potato milk",   "banana milk",    "walnut milk",
    }),
    # "cream" — plant-based versions
    "cream": frozenset({
        "coconut cream", "oat cream", "cashew cream", "almond cream",
    }),
    # "egg" mid-word false positives
    "egg": frozenset({
        "eggplant",
    }),
}
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# 2.  ALLERGEN SYNONYM DATABASE
# ═══════════════════════════════════════════════════════════════════════════════
# Keys   = canonical allergen name (matches what a user would select in the UI).
# Values = set of lowercase tokens / phrases that indicate the allergen is
#           present in an ingredient list.  Includes scientific names, common
#           derivatives, and food-industry abbreviations.
#
# Sources: FDA "Big 9" guidance, FARE (Food Allergy Research & Education),
#          EU FIC Annex II, Codex Alimentarius.
 
ALLERGEN_SYNONYMS: dict[str, set[str]] = {
 
    # ── FDA Big 9 ─────────────────────────────────────────────────────────────
 
    "Milk": {
        "milk", "whole milk", "skim milk", "nonfat milk", "lowfat milk",
        "milk powder", "dry milk", "milk solids", "milk fat",
        "cream", "half and half", "half & half",
        "butter", "butterfat", "buttermilk", "butter oil", "ghee",
        "cheese", "cheddar", "parmesan", "mozzarella", "ricotta", "brie",
        "cream cheese", "cottage cheese", "goat cheese",
        "yogurt", "yoghurt", "kefir",
        "casein", "caseinate", "sodium caseinate", "calcium caseinate",
        "casein hydrolysate",
        "whey", "whey protein", "whey powder", "sweet whey",
        "acid whey", "whey protein concentrate", "whey protein isolate",
        "lactalbumin", "lactalbumin phosphate",
        "lactoglobulin", "beta-lactoglobulin",
        "lactoferrin", "lactose", "lactulose",
        "curds", "custard", "pudding",
        "galactose", "recaldent", "rennet casein", "tagatose",
        "nisin",   # antimicrobial from milk fermentation
    },
 
    "Eggs": {
        "egg", "eggs", "egg white", "egg yolk", "egg wash",
        "dried egg", "powdered egg", "egg powder", "egg solids",
        "albumin", "albumen",
        "globulin", "ovoglobulin",
        "lysozyme",
        "mayonnaise", "mayo",
        "meringue",
        "ovalbumin", "ovomucin", "ovomucoid", "ovovitellin",
        "silici albuminate",
        "simplesse",    # fat replacer made from egg white
        "livetin",
        "eggnog",
    },
 
    "Peanuts": {
        "peanut", "peanuts", "peanut butter", "peanut flour",
        "peanut oil", "peanut protein",
        "arachis oil", "arachis hypogaea",
        "groundnut", "groundnuts",
        "beer nuts", "mixed nuts",
        "monkey nuts",
        "mandelonas",     # peanuts soaked in almond flavour
        "nu-nuts",
        "nutmeat",
        "goobers",
    },
 
    "Tree Nuts": {
        "almond", "almonds", "almond butter", "almond milk", "almond flour",
        "almond extract", "marzipan", "amaretto",
        "brazil nut", "brazil nuts",
        "cashew", "cashews", "cashew butter",
        "chestnut", "chestnuts",
        "coconut",   # FDA classifies coconut as a tree nut
        "filbert", "filberts",
        "hazelnut", "hazelnuts", "hazelnut butter", "gianduja", "praline",
        "macadamia", "macadamias", "macadamia nut",
        "pecan", "pecans",
        "pine nut", "pine nuts", "pignoli", "pinon",
        "pistachio", "pistachios",
        "walnut", "walnuts",
        "shea nut",
        "nougat",
        "nut butter", "nut meal", "nut paste", "nut oil", "nut extract",
        "tree nut", "tree nuts",
    },
 
    "Fish": {
        "fish", "cod", "salmon", "tuna", "tilapia", "trout", "bass",
        "haddock", "halibut", "herring", "mackerel", "perch", "pike",
        "pollock", "sardine", "sardines", "snapper", "sole", "swordfish",
        "anchovy", "anchovies",
        "fish oil", "fish gelatin", "fish sauce",
        "surimi", "imitation crab",
        "worcestershire sauce",   # commonly contains anchovies
        "caesar dressing",        # commonly contains anchovies
        "nam pla", "nuoc mam",   # fish sauce variants
    },
 
    "Shellfish": {
        "shellfish", "shrimp", "prawn", "prawns",
        "crab", "crabmeat", "imitation crab",
        "lobster", "crawfish", "crayfish", "langoustine",
        "clam", "clams",
        "mussel", "mussels",
        "oyster", "oysters", "oyster sauce",
        "scallop", "scallops",
        "squid", "calamari",
        "snail", "escargot",
        "abalone", "cockle", "cuttlefish", "limpet", "octopus",
        "sea urchin", "uni",
        "chitosan",     # derived from crustacean shells
        "glucosamine",  # often from shellfish
    },
 
    "Wheat": {
        "wheat", "wheat flour", "whole wheat", "wheat starch",
        "wheat bran", "wheat germ", "wheat gluten", "wheat grass",
        "wheat protein", "hydrolysed wheat protein",
        "bread crumbs", "breadcrumbs",
        "bulgur", "couscous", "cracker meal",
        "durum", "durum flour",
        "einkorn", "emmer",
        "farina",
        "flour",   # unqualified "flour" is almost always wheat
        "freekeh", "graham flour",
        "kamut", "khorasan",
        "matzoh", "matzo", "matzah",
        "orzo",    # wheat pasta
        "pasta",   # default pasta = wheat
        "seitan", "semolina", "spelt", "triticale",
        "vital wheat gluten",
        "enriched flour", "bleached flour", "unbleached flour",
        "all-purpose flour", "all purpose flour",
        "bread flour", "cake flour", "pastry flour", "self-rising flour",
    },
 
    "Soy": {
        "soy", "soya", "soybean", "soybeans", "soy bean",
        "soy flour", "soy protein", "soy protein isolate",
        "soy sauce", "shoyu", "tamari",
        "soy lecithin", "soya lecithin",
        "soy milk", "soy oil", "soybean oil",
        "edamame", "miso", "natto", "tempeh",
        "textured vegetable protein", "tvp",
        "tofu", "bean curd",
        "hydrolysed soy protein",
        "soy albumin", "soy fiber", "soy fibre", "soy grits", "soy nuts",
    },
 
    "Sesame": {
        "sesame", "sesame seed", "sesame seeds",
        "sesame oil", "sesame paste", "sesame flour",
        "tahini", "tahina",
        "halvah", "halva",
        "hummus",         # traditionally contains tahini
        "gomashio", "gomasio",
        "benne seeds",    # regional name for sesame
        "gingelly oil",   # sesame oil in South Asia
        "til", "til oil", # sesame in Hindi
    },
 
    # ── Extended allergens (not Big 9 but common) ────────────────────────────
 
    "Gluten": {
        "gluten", "wheat gluten", "vital wheat gluten",
        "barley", "barley malt", "malt", "malt extract", "malt vinegar",
        "rye", "rye flour",
        "oat", "oats", "oat flour",   # unless certified GF
        "triticale", "spelt", "kamut", "einkorn", "emmer", "farro",
        "seitan",
        "brewer's yeast",
        "hydrolysed wheat protein",
        "modified food starch",   # may be wheat-derived
    },
 
    "Sulfites": {
        "sulfite", "sulfites", "sulphite", "sulphites",
        "sulfur dioxide", "sulphur dioxide",
        "sodium sulfite", "sodium bisulfite", "sodium metabisulfite",
        "potassium bisulfite", "potassium metabisulfite",
        "e220", "e221", "e222", "e223", "e224", "e225", "e226", "e227", "e228",
    },
 
    "Mustard": {
        "mustard", "mustard seed", "mustard flour", "mustard oil",
        "mustard powder", "prepared mustard", "dijon",
    },
 
    "Celery": {
        "celery", "celery seed", "celery salt", "celery powder", "celeriac",
    },
 
    "Lupin": {
        "lupin", "lupine", "lupini", "lupini beans",
    },
 
    "Mollusks": {
        "mollusk", "mollusc", "snail", "escargot",
        "clam", "mussel", "oyster", "scallop",
        "squid", "calamari", "octopus", "cuttlefish",
        "abalone", "whelk", "periwinkle",
    },
 
    "Corn": {
        "corn", "maize", "corn flour", "cornmeal", "cornstarch",
        "corn starch", "corn syrup", "high fructose corn syrup", "hfcs",
        "corn oil", "corn protein", "dextrose", "maltodextrin",
        "polenta", "hominy", "grits",
    },
 
    "Latex-Fruit": {
        # Cross-reactive with latex allergy
        "banana", "avocado", "kiwi", "chestnut",
        "papaya", "mango", "passion fruit",
    },
}
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# 3.  DIET INCOMPATIBILITY RULES
# ═══════════════════════════════════════════════════════════════════════════════
# Each diet maps to a set of ingredient keywords that VIOLATE it.
# The engine checks every parsed ingredient token against these sets.
 
DIET_RULES: dict[str, dict] = {
 
    "Vegan": {
        "description": "No animal-derived ingredients",
        "forbidden": {
            # Dairy
            "milk", "cream", "butter", "cheese", "whey", "casein",
            "caseinate", "lactose", "yogurt", "ghee", "buttermilk",
            "lactalbumin", "lactoglobulin", "curds",
            # Eggs
            "egg", "eggs", "albumin", "albumen", "mayonnaise", "mayo",
            "meringue", "lysozyme", "ovalbumin",
            # Meat / Poultry
            "chicken", "beef", "pork", "turkey", "lamb", "veal",
            "bacon", "ham", "sausage", "salami", "pepperoni",
            "gelatin", "gelatine", "lard", "tallow", "suet",
            "bone meal", "bone broth", "collagen",
            # Fish / Shellfish
            "fish", "anchovy", "anchovies", "sardine", "tuna", "salmon",
            "shrimp", "prawn", "crab", "lobster", "oyster", "mussel",
            "squid", "calamari", "fish sauce", "fish oil",
            "surimi", "chitosan",
            # Honey / Bee products
            "honey", "beeswax", "royal jelly", "propolis",
            # Other
            "carmine", "cochineal",
            "shellac", "confectioner's glaze",
            "isinglass",
            "rennet",
            "vitamin d3",
            "omega-3",
        },
    },
 
    "Vegetarian": {
        "description": "No meat, poultry, fish, or slaughter by-products",
        "forbidden": {
            "chicken", "beef", "pork", "turkey", "lamb", "veal",
            "bacon", "ham", "sausage", "salami", "pepperoni",
            "gelatin", "gelatine", "lard", "tallow", "suet",
            "bone meal", "bone broth", "collagen",
            "fish", "anchovy", "anchovies", "sardine", "tuna", "salmon",
            "shrimp", "prawn", "crab", "lobster", "oyster", "mussel",
            "squid", "calamari", "fish sauce", "fish oil",
            "surimi", "chitosan",
            "rennet",
            "isinglass",
            "carmine", "cochineal",
        },
    },
 
    "Gluten-Free": {
        "description": "No gluten-containing grains",
        "forbidden": {
            "wheat", "wheat flour", "whole wheat", "bread flour",
            "all-purpose flour", "all purpose flour", "flour",
            "enriched flour", "bleached flour", "unbleached flour",
            "cake flour", "pastry flour", "self-rising flour",
            "gluten", "wheat gluten", "vital wheat gluten", "seitan",
            "barley", "barley malt", "malt", "malt extract", "malt vinegar",
            "rye", "rye flour",
            "triticale", "spelt", "kamut", "einkorn", "emmer", "farro",
            "bulgur", "couscous", "freekeh", "farina", "semolina",
            "durum", "durum flour", "graham flour",
            "orzo", "pasta",
            "bread crumbs", "breadcrumbs", "cracker meal",
            "brewer's yeast",
        },
    },
 
    "Dairy-Free": {
        "description": "No milk or milk-derived ingredients",
        "forbidden": {
            "milk", "whole milk", "skim milk", "milk powder", "milk solids",
            "milk fat", "cream", "half and half", "butter", "butterfat",
            "buttermilk", "ghee", "cheese", "yogurt", "yoghurt", "kefir",
            "casein", "caseinate", "sodium caseinate",
            "whey", "whey protein", "whey powder",
            "lactalbumin", "lactoglobulin", "lactose", "lactoferrin",
            "curds", "custard",
        },
    },
 
    "Keto": {
        "description": "Very low carbohydrate; avoid sugars, grains, starches",
        "forbidden": {
            "sugar", "cane sugar", "brown sugar", "powdered sugar",
            "corn syrup", "high fructose corn syrup", "hfcs",
            "honey", "agave", "maple syrup", "molasses",
            "dextrose", "maltose", "sucrose", "fructose",
            "flour", "wheat flour", "rice flour", "corn flour",
            "rice", "pasta", "bread", "oats", "oat",
            "potato", "potato starch", "cornstarch", "corn starch",
            "tapioca", "tapioca starch",
            "maltodextrin",
        },
    },
 
    "Paleo": {
        "description": "No grains, legumes, dairy, refined sugar, or processed oils",
        "forbidden": {
            # Grains
            "wheat", "flour", "rice", "corn", "oats", "oat", "barley",
            "rye", "quinoa", "pasta", "bread",
            # Legumes
            "soy", "soybean", "soy lecithin", "peanut", "lentil",
            "chickpea", "black bean", "kidney bean",
            # Dairy
            "milk", "cheese", "cream", "butter", "yogurt", "whey",
            "casein", "lactose",
            # Refined sugar
            "sugar", "corn syrup", "high fructose corn syrup",
            "dextrose", "maltodextrin",
            # Processed oils
            "canola oil", "soybean oil", "vegetable oil",
            "corn oil", "sunflower oil", "safflower oil",
        },
    },
 
    "Halal": {
        "description": "No pork, alcohol, or non-halal slaughtered meat",
        "forbidden": {
            "pork", "ham", "bacon", "lard", "pancetta", "prosciutto",
            "pepperoni", "salami",
            "gelatin", "gelatine",   # unless certified halal
            "alcohol", "ethanol", "wine", "beer", "rum", "bourbon",
            "vanilla extract",       # often alcohol-based
        },
    },
 
    "Kosher": {
        "description": "No pork, shellfish, or mixing meat and dairy",
        "forbidden": {
            "pork", "ham", "bacon", "lard", "pancetta",
            "shellfish", "shrimp", "prawn", "crab", "lobster",
            "oyster", "mussel", "clam", "scallop",
            "squid", "calamari", "octopus",
            "gelatin", "gelatine",   # unless kosher-certified
        },
    },
}
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# 4.  CROSS-CONTAMINATION / ADVISORY PHRASES
# ═══════════════════════════════════════════════════════════════════════════════
 
_ADVISORY_PATTERNS: list[re.Pattern] = [
    re.compile(r"may\s+contain\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"produced\s+in\s+a\s+facility\s+(?:that\s+)?(?:also\s+)?(?:processes|handles|uses)\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"manufactured\s+(?:on|in)\s+(?:shared\s+)?(?:equipment|lines?)\s+(?:with|that\s+(?:also\s+)?process(?:es)?)\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"(?:shared\s+facility|cross[- ]?contact)\s+(?:with\s+)?(.+?)(?:\.|$)", re.I),
    re.compile(r"contains?\s+(.+?)\s+ingredients?", re.I),
]
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# 5.  INGREDIENT PARSER
# ═══════════════════════════════════════════════════════════════════════════════
 
def parse_ingredients(raw: str) -> list[str]:
    """
    Tokenise a product ingredient string into individual normalised tokens.
 
    Handles:
      • comma / semicolon separation
      • nested parentheses  e.g. "chocolate (sugar, cocoa butter, milk)"
      • pipe-delimited OFF data
      • percentage annotations  e.g. "sugar (12%)"
      • trailing periods, colons, and "CONTAINS:" / "INGREDIENTS:" prefixes
 
    Returns lowercase, stripped, deduplicated tokens in original order.
    """
    if not raw:
        return []
 
    text = raw.strip()
    text = re.sub(r"^(?:ingredients?\s*:?\s*)", "", text, flags=re.I)
    text = re.sub(r"\(([^)]*)\)", lambda m: ", " + m.group(1), text)
    text = text.replace("|", ",").replace(";", ",")
    text = re.sub(r"\d+(\.\d+)?\s*%", "", text)
 
    seen: set[str] = set()
    tokens: list[str] = []
    for chunk in text.split(","):
        t = chunk.strip().strip(".").strip(":").lower()
        t = re.sub(r"\s+", " ", t)
        if t and t not in seen:
            seen.add(t)
            tokens.append(t)
 
    return tokens
 
 
def _extract_advisory_allergens(raw: str) -> list[str]:
    """
    Pull allergen names from advisory / cross-contamination statements.
    Returns a list of lowercase allergen tokens found in advisory phrases.
    """
    results: list[str] = []
    for pat in _ADVISORY_PATTERNS:
        for match in pat.finditer(raw):
            fragment = match.group(1)
            for part in re.split(r"[,&]|\band\b", fragment):
                part = part.strip().lower().rstrip(".")
                if part and len(part) > 1:
                    results.append(part)
    return results
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# 6.  ALLERGEN DETECTION
# ═══════════════════════════════════════════════════════════════════════════════
 
@dataclass
class AllergenMatch:
    allergen:        str              # canonical name, e.g. "Milk"
    matched_token:   str              # the ingredient token that triggered match
    confidence:      Confidence
    severity:        Severity
    is_advisory:     bool = False     # True when matched via "may contain" language
 
    def to_dict(self) -> dict:
        return asdict(self)
 
 
def detect_allergens(
    ingredients_text: str,
    user_allergens: list[str],
) -> list[AllergenMatch]:
    """
    Detect which of the user's declared allergens appear in the ingredient text.
 
    Multi-pass matching strategy:
      Pass 1 — exact token match against synonym sets          → DEFINITE
      Pass 2 — substring match with compound exclusion check   → PROBABLE
               All substring matches are PROBABLE regardless of word boundary.
               Recall > Precision: even derivative matches (sodium caseinate)
               trigger a hard stop. Compound exclusion lists handle known
               plant-based false positives (cocoa butter, oat milk, etc.).
      Pass 3 — advisory phrase extraction ("may contain" etc.)  → PROBABLE
               Promoted from POSSIBLE so advisory language triggers the
               ALLERGEN hard stop (DONT_BUY), not just a soft caution signal.
               The is_advisory=True flag lets notifications show distinct wording:
                 "label warns may contain X" vs "X confirmed in ingredient list".
 
    Both DEFINITE and PROBABLE trigger the Layer 1 ALLERGEN hard stop.
    Returns a list of AllergenMatch objects, deduplicated by (allergen, token).
    """
    if not ingredients_text or not user_allergens:
        return []
 
    tokens = parse_ingredients(ingredients_text)
    raw_lower = ingredients_text.lower()
    matches: dict[tuple[str, str], AllergenMatch] = {}
 
    for allergen_name in user_allergens:
        synonyms = ALLERGEN_SYNONYMS.get(allergen_name)
        if synonyms is None:
            for key, val in ALLERGEN_SYNONYMS.items():
                if key.lower() == allergen_name.lower():
                    allergen_name = key
                    synonyms = val
                    break
        if synonyms is None:
            continue
 
        severity = (
            Severity.HIGH if allergen_name in _HIGH_SEVERITY_ALLERGENS
            else Severity.MEDIUM
        )
 
        # ── Pass 1: exact token match ─────────────────────────────────────────
        for token in tokens:
            if token in synonyms:
                key = (allergen_name, token)
                if key not in matches:
                    matches[key] = AllergenMatch(
                        allergen=allergen_name,
                        matched_token=token,
                        confidence=Confidence.DEFINITE,
                        severity=severity,
                    )
 
        # ── Pass 2: substring / partial match ─────────────────────────────────
        #   Catches cases like "sodium caseinate" (contains "casein", a Milk
        #   synonym) or "hydrolysed wheat protein" (contains "wheat").
        #
        #   Compound exclusion: skip tokens in ALLERGEN_COMPOUND_EXCLUSIONS for
        #   this synonym to avoid plant-based false positives:
        #   "butter" in "cocoa butter" → excluded (not dairy butter)
        #   "butter" in "peanut butter" → excluded (not dairy butter)
        #   "milk" in "oat milk" → excluded (not dairy milk)
        for synonym in synonyms:
            if len(synonym) < 3:
                continue
            for token in tokens:
                if synonym not in token:
                    continue
                if (allergen_name, token) in matches:
                    continue
                # Compound exclusion check.
                # The exclusion dict is keyed by the SHORT trigger word, not the
                # full synonym string. "wheat flour" (a multi-word synonym) hits
                # "buckwheat flour" — we need to check each word of the synonym
                # against the exclusion dict, not the full synonym string.
                # e.g. synonym="wheat flour" → check keys "wheat" AND "flour".
                # If the token is excluded under ANY of those root words, skip it.
                synonym_words = synonym.split()
                is_excluded = False
                for word in synonym_words:
                    excluded_tokens = ALLERGEN_COMPOUND_EXCLUSIONS.get(word, frozenset())
                    if token in excluded_tokens:
                        is_excluded = True
                        break
                # Also check the full synonym string as a key (original behaviour)
                if not is_excluded:
                    excluded_tokens = ALLERGEN_COMPOUND_EXCLUSIONS.get(synonym, frozenset())
                    if token in excluded_tokens:
                        is_excluded = True
                if is_excluded:
                    continue
                matches[(allergen_name, token)] = AllergenMatch(
                    allergen=allergen_name,
                    matched_token=token,
                    confidence=Confidence.PROBABLE,
                    severity=severity,
                )
 
        # ── Pass 3: advisory / "may contain" phrases ──────────────────────────
        #   Matches phrases like "May Contain Peanuts", "Produced in a facility
        #   that also processes milk", "Shared facility with tree nuts", etc.
        #
        #   Confidence = PROBABLE (not POSSIBLE) so that the ALLERGEN hard stop
        #   fires and the product returns DONT_BUY.  Advisory language on a
        #   product label is a real safety signal for allergy sufferers —
        #   treating it as only a soft caution can lead to dangerous outcomes.
        #
        #   The is_advisory=True flag is preserved so _build_notifications() in
        #   risk_routes.py can show distinct message wording:
        #     PROBABLE + is_advisory=False  → "Contains X — detected in ingredient list"
        #     PROBABLE + is_advisory=True   → "Label warns this product may contain X"
        advisory_tokens = _extract_advisory_allergens(raw_lower)
        for adv_token in advisory_tokens:
            if adv_token in synonyms or any(s in adv_token for s in synonyms if len(s) >= 3):
                key = (allergen_name, f"advisory:{adv_token}")
                if key not in matches:
                    matches[key] = AllergenMatch(
                        allergen=allergen_name,
                        matched_token=adv_token,
                        confidence=Confidence.PROBABLE,   # promotes advisory → hard stop
                        severity=severity,
                        is_advisory=True,
                    )
 
    return list(matches.values())
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# 7.  DIET INCOMPATIBILITY CHECK
# ═══════════════════════════════════════════════════════════════════════════════
 
@dataclass
class DietFlag:
    diet:          str            # e.g. "Vegan"
    flagged_token: str            # the ingredient that violated the diet
    reason:        str            # human-readable explanation
    confidence:    Confidence
 
    def to_dict(self) -> dict:
        return asdict(self)
 
 
def check_diet_compatibility(
    ingredients_text: str,
    user_diets: list[str],
) -> list[DietFlag]:
    """
    Check each declared diet against the ingredient list.
 
    Matching strategy:
      Pass 1 — exact token match in forbidden set          → DEFINITE
      Pass 2 — substring with word-boundary discrimination:
               whole-word compound match (e.g. "gelatin" in "beef gelatin")
                 → DEFINITE  (triggers hard stop for strict diets)
               subword match (e.g. "gelatin" in "gelatinous")
                 → PROBABLE  (soft caution signal only)
      Both passes check DIET_COMPOUND_EXCLUSIONS to skip plant-based
      false positives (cocoa butter, oat milk, eggplant, etc.).
 
    Returns a list of DietFlag objects, one per (diet, flagged ingredient) pair.
    """
    if not ingredients_text or not user_diets:
        return []
 
    tokens = parse_ingredients(ingredients_text)
    flags: list[DietFlag] = []
    seen: set[tuple[str, str]] = set()
 
    for diet_name in user_diets:
        rules = DIET_RULES.get(diet_name)
        if rules is None:
            for key, val in DIET_RULES.items():
                if key.lower() == diet_name.lower():
                    diet_name = key
                    rules = val
                    break
        if rules is None:
            continue
 
        forbidden: set[str] = rules["forbidden"]
        description: str = rules["description"]
 
        for token in tokens:
            # ── Pass 1: exact match ───────────────────────────────────────────
            if token in forbidden:
                key = (diet_name, token)
                if key not in seen:
                    seen.add(key)
                    flags.append(DietFlag(
                        diet=diet_name,
                        flagged_token=token,
                        reason=f"'{token}' is incompatible with {diet_name} ({description})",
                        confidence=Confidence.DEFINITE,
                    ))
                continue
 
            # ── Pass 2: substring with word-boundary discrimination ────────────
            for forbidden_item in forbidden:
                if len(forbidden_item) < 3:
                    continue
                if forbidden_item not in token:
                    continue   # fast pre-check before regex
 
                # Compound exclusion: skip plant-derived compounds that contain
                # a forbidden word but are not the animal product.
                # e.g. "cocoa butter" should not violate the Vegan "butter" rule.
                # e.g. "eggplant" should not violate the Vegan "egg" rule.
                excluded_tokens = DIET_COMPOUND_EXCLUSIONS.get(forbidden_item, frozenset())
                if token in excluded_tokens:
                    continue
 
                key = (diet_name, token)
                if key in seen:
                    break
 
                # Word-boundary check: determines whether forbidden_item appears
                # as a complete word inside the token (whole-word → DEFINITE) or
                # as a fragment of a longer word (subword → PROBABLE).
                # "gelatin" in "beef gelatin" → \bgelatin\b matches → DEFINITE
                # "gelatin" in "gelatinous"   → \bgelatin\b no match → PROBABLE
                whole_word = bool(re.search(
                    r'\b' + re.escape(forbidden_item) + r'\b', token
                ))
                seen.add(key)
                if whole_word:
                    flags.append(DietFlag(
                        diet=diet_name,
                        flagged_token=token,
                        reason=(
                            f"'{token}' contains '{forbidden_item}', "
                            f"incompatible with {diet_name} ({description})"
                        ),
                        confidence=Confidence.DEFINITE,
                    ))
                else:
                    flags.append(DietFlag(
                        diet=diet_name,
                        flagged_token=token,
                        reason=(
                            f"'{token}' likely contains '{forbidden_item}', "
                            f"incompatible with {diet_name}"
                        ),
                        confidence=Confidence.PROBABLE,
                    ))
                break
 
    return flags
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# 8.  TWO-LAYER VERDICT SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
#
#   Layer 1 – HARD STOPS (binary gates) — evaluated first
#     If ANY gate fires → verdict = DONT_BUY, Layer 2 skipped entirely.
#       Gate 1: RECALL      — active FDA recall
#       Gate 2: ALLERGEN    — DEFINITE or PROBABLE allergen match
#                             (includes advisory "may contain" language)
#       Gate 3: DIET_STRICT — DEFINITE violation of a strict diet
#                             (Vegan, Vegetarian, Gluten-Free, Dairy-Free,
#                              Halal, Kosher — not Keto or Paleo)
#
#   Layer 2 – SOFT CAUTION SIGNALS — only when no hard stop fired
#
#     ADDITIVE signals (is_safety_risk=False):
#       Any single flagged additive → CAUTION immediately.
#       No point accumulation required — the presence of any additive is
#       sufficient to flip the verdict. The is_safety_risk=False flag tells
#       the frontend to render a softer badge than allergen/recall CAUTION.
#
#     Point-based signals (accumulate toward CAUTION_THRESHOLD=15):
#       DIET_SOFT (is_safety_risk=False):
#         • PROBABLE diet flag (subword match) → 5 pts
#         • DEFINITE violation on non-strict diet (Keto/Paleo) → 4 pts
#       LOW_CONFIDENCE (is_safety_risk=True):
#         • Missing ingredient list entirely → 12 pts
#         • Ingredient list unusually short (<2 tokens) → 8 pts
#       CROSS_CONTACT (is_safety_risk=True):
#         • POSSIBLE-confidence allergen match → 8 pts
#         • Reserved — not currently assigned by the deterministic engine.
#
#     Verdict rule (Layer 2 only):
#       any ADDITIVE signal present                           → CAUTION
#       no ADDITIVE but non-additive point score ≥ threshold → CAUTION
#       otherwise                                            → OK
#
# ═══════════════════════════════════════════════════════════════════════════════
 
class Verdict(str, Enum):
    OK       = "OK"
    CAUTION  = "CAUTION"
    DONT_BUY = "DONT_BUY"
 
 
# Diets treated as strict (medical / ethical non-negotiables).
# Non-strict diets (Keto, Paleo) produce caution signals, never hard stops.
_STRICT_DIETS = frozenset({
    "Gluten-Free", "Dairy-Free", "Vegan", "Vegetarian", "Halal", "Kosher",
})
 
# Score threshold for non-additive soft signals to flip verdict to CAUTION.
# ADDITIVE signals bypass this threshold entirely — any single additive
# triggers CAUTION directly regardless of accumulated score.
CAUTION_THRESHOLD = 15
 
 
# ── Known controversial additives ─────────────────────────────────────────────
# Values are plain description strings only — no point score.
# Any single match triggers CAUTION directly (threshold not used for additives).
# is_safety_risk=False on all additive signals — health preference, not medical emergency.
 
FLAGGED_ADDITIVES: dict[str, str] = {
    "high fructose corn syrup": "Linked to metabolic concerns",
    "hfcs":                     "High fructose corn syrup — linked to metabolic concerns",
    "aspartame":                "Artificial sweetener; some individuals sensitive",
    "sucralose":                "Artificial sweetener",
    "acesulfame potassium":     "Artificial sweetener (Ace-K)",
    "acesulfame k":             "Artificial sweetener (Ace-K)",
    "sodium nitrite":           "Preservative in processed meats",
    "sodium nitrate":           "Preservative in processed meats",
    "bha":                      "Synthetic antioxidant preservative",
    "bht":                      "Synthetic antioxidant preservative",
    "tbhq":                     "Synthetic preservative",
    "monosodium glutamate":     "MSG; some individuals report sensitivity",
    "msg":                      "Monosodium glutamate; some individuals report sensitivity",
    "carrageenan":              "Thickener; debated GI effects",
    "sodium benzoate":          "Preservative; may form benzene with vitamin C",
    "potassium bromate":        "Flour improver; banned in many countries",
    "propylparaben":            "Preservative; endocrine disruptor concerns",
    "titanium dioxide":         "Colour additive; banned in EU food since 2022",
    "red 40":                   "Synthetic dye; linked to hyperactivity in some children",
    "red dye 40":               "Synthetic dye; linked to hyperactivity in some children",
    "yellow 5":                 "Synthetic dye (tartrazine)",
    "yellow 6":                 "Synthetic dye (sunset yellow)",
    "blue 1":                   "Synthetic dye (brilliant blue)",
    "partially hydrogenated":   "Source of artificial trans fats",
    "hydrogenated oil":         "May contain trans fats",
}
 
_MIN_INGREDIENTS_FOR_CONFIDENCE = 2
 
 
# ── Layer 1: Hard stops ───────────────────────────────────────────────────────
 
@dataclass
class HardStop:
    gate:    str            # RECALL | ALLERGEN | DIET_STRICT
    reason:  str            # human-readable explanation bullet
    allergen: str = ""      # canonical allergen name for ALLERGEN gate; "" otherwise
    diet:     str = ""      # diet name for DIET_STRICT gate; "" otherwise
 
 
def _evaluate_hard_stops(
    is_recalled: bool,
    recall_date: Optional[str],
    allergen_matches: list[AllergenMatch],
    diet_flags: list[DietFlag],
    strict_diets: frozenset[str],
) -> list[HardStop]:
    stops: list[HardStop] = []
 
    # Gate 1: active recall
    if is_recalled:
        date_part = f" on {recall_date}" if recall_date else ""
        stops.append(HardStop(
            "RECALL",
            f"Active FDA recall reported{date_part}. "
            f"Do not consume this product — check the recall details for "
            f"return/refund instructions.",
        ))
 
    # Gate 2: confirmed allergen (DEFINITE or PROBABLE, including advisory)
    seen_allergens: set[str] = set()
    for m in allergen_matches:
        if m.confidence in (Confidence.DEFINITE, Confidence.PROBABLE) \
                and m.allergen not in seen_allergens:
            seen_allergens.add(m.allergen)
 
            severity_note = (
                f"{m.allergen} is an FDA Big 9 allergen that can cause severe "
                f"allergic reactions including anaphylaxis."
                if m.allergen in _HIGH_SEVERITY_ALLERGENS
                else f"{m.allergen} is a known allergen that can cause allergic reactions."
            )
 
            if m.is_advisory:
                stops.append(HardStop(
                    "ALLERGEN",
                    f"Label warns this product may contain {m.allergen.lower()} "
                    f"(your declared allergen) — '{m.matched_token}' detected in "
                    f"the advisory/cross-contact statement on the label. "
                    f"{severity_note}",
                    allergen=m.allergen,
                ))
            elif m.confidence == Confidence.DEFINITE:
                stops.append(HardStop(
                    "ALLERGEN",
                    f"Contains {m.allergen.lower()} (your declared allergen) — "
                    f"detected '{m.matched_token}' in the ingredient list. "
                    f"{severity_note}",
                    allergen=m.allergen,
                ))
            else:
                stops.append(HardStop(
                    "ALLERGEN",
                    f"Likely contains {m.allergen.lower()} (your declared allergen) — "
                    f"'{m.matched_token}' is a known derivative of "
                    f"{m.allergen.lower()}. {severity_note}",
                    allergen=m.allergen,
                ))
 
    # Gate 3: strict diet violation (DEFINITE only)
    seen_diets: set[str] = set()
    for f in diet_flags:
        if f.confidence == Confidence.DEFINITE \
                and f.diet in strict_diets \
                and f.diet not in seen_diets:
            seen_diets.add(f.diet)
            diet_desc = DIET_RULES.get(f.diet, {}).get("description", "")
            stops.append(HardStop(
                "DIET_STRICT",
                (
                    f"Not {f.diet} — '{f.flagged_token}' is incompatible. "
                    f"{f.diet} means {diet_desc.lower()}."
                ) if diet_desc else
                f"Not {f.diet} — contains '{f.flagged_token}'.",
                diet=f.diet,
            ))
 
    return stops
 
 
# ── Layer 2: Soft caution signals ─────────────────────────────────────────────
 
@dataclass
class CautionSignal:
    category:       str    # CROSS_CONTACT | ADDITIVE | DIET_SOFT | LOW_CONFIDENCE
    detail:         str    # human-readable explanation bullet
    points:         int    # used for threshold scoring — ADDITIVE always uses 0
    is_safety_risk: bool = True
    # is_safety_risk=False for ADDITIVE and DIET_SOFT — these are health-preference
    # concerns, not medical emergencies. Frontend should render a softer badge style
    # (e.g. amber info vs amber warning) to distinguish from safety-critical CAUTION.
 
 
def _evaluate_caution_signals(
    allergen_matches: list[AllergenMatch],
    diet_flags: list[DietFlag],
    parsed_ingredients: list[str],
    strict_diets: frozenset[str],
    ingredients_text: str,
) -> list[CautionSignal]:
    """
    Layer 2: soft caution signals. Only runs when no hard stop fired.
 
    Two distinct sub-systems:
 
    A) ADDITIVE signals — bypass threshold entirely.
       Any single flagged additive immediately makes the product CAUTION.
       points=0 for all additive signals (threshold is irrelevant).
       is_safety_risk=False — health preference, not a medical allergen concern.
       Frontend should render additive CAUTION with a softer badge than
       allergen or recall CAUTION.
 
    B) Point-based signals — accumulate toward CAUTION_THRESHOLD (15 pts).
       DIET_SOFT:      PROBABLE diet flag (5 pts) or DEFINITE on non-strict
                       diet Keto/Paleo (4 pts). is_safety_risk=False.
       LOW_CONFIDENCE: missing ingredient list (12 pts) or unusually short
                       list (8 pts). is_safety_risk=True.
       CROSS_CONTACT:  POSSIBLE-confidence allergen (8 pts). is_safety_risk=True.
                       Reserved — not currently assigned by deterministic engine.
 
    The verdict in analyse_product_risk() checks additive presence separately
    from the point threshold, so both sub-systems operate independently.
    """
    signals: list[CautionSignal] = []
 
    # ── CROSS_CONTACT — reserved for POSSIBLE-confidence matches (future use) ──
    # Advisory "may contain" matches are PROBABLE → handled by Layer 1 hard stop.
    seen: set[str] = set()
    for m in allergen_matches:
        if m.confidence == Confidence.POSSIBLE and m.allergen not in seen:
            seen.add(m.allergen)
            signals.append(CautionSignal(
                "CROSS_CONTACT",
                f"Advisory: may contain traces of {m.allergen.lower()} — "
                f"possible cross-contamination. Not confirmed in the "
                f"ingredient list.",
                8,
                is_safety_risk=True,
            ))
 
    # ── DIET_SOFT — PROBABLE diet flags or DEFINITE on non-strict diets ────────
    # is_safety_risk=False: diet preference conflicts are not medical emergencies.
    seen_dt: set[tuple[str, str]] = set()
    for f in diet_flags:
        key = (f.diet, f.flagged_token)
        if key in seen_dt:
            continue
        seen_dt.add(key)
        diet_desc = DIET_RULES.get(f.diet, {}).get("description", "")
        if f.confidence == Confidence.PROBABLE:
            signals.append(CautionSignal(
                "DIET_SOFT",
                f"Possibly not {f.diet} — '{f.flagged_token}' may be "
                f"incompatible. Could not confirm from the label text alone.",
                5,
                is_safety_risk=False,
            ))
        elif f.confidence == Confidence.DEFINITE and f.diet not in strict_diets:
            signals.append(CautionSignal(
                "DIET_SOFT",
                (
                    f"Not {f.diet} — contains '{f.flagged_token}'. "
                    f"{f.diet} avoids this because: {diet_desc.lower()}."
                ) if diet_desc else
                f"Not {f.diet} — contains '{f.flagged_token}'.",
                4,
                is_safety_risk=False,
            ))
 
    # ── ADDITIVE — any single flagged additive triggers CAUTION directly ────────
    # No threshold accumulation. points=0 for all additive signals.
    # is_safety_risk=False — additive concerns are health preferences, not
    # medical allergen risks. Frontend renders a distinct softer badge style.
    seen_additives: set[str] = set()
    for token in parsed_ingredients:
        # Exact key match
        desc = FLAGGED_ADDITIVES.get(token)
        if desc and token not in seen_additives:
            seen_additives.add(token)
            signals.append(CautionSignal(
                "ADDITIVE",
                f"Contains '{token}' — {desc}. "
                f"This additive is legal but flagged by health-conscious consumers.",
                0,
                is_safety_risk=False,
            ))
            continue
        # Substring match for multi-word additive keys (e.g. "partially hydrogenated"
        # inside "partially hydrogenated soybean oil")
        for additive_key, desc in FLAGGED_ADDITIVES.items():
            if len(additive_key) >= 5 and additive_key in token \
                    and additive_key not in seen_additives:
                seen_additives.add(additive_key)
                signals.append(CautionSignal(
                    "ADDITIVE",
                    f"Contains '{token}' — {desc}. "
                    f"This additive is legal but flagged by health-conscious consumers.",
                    0,
                    is_safety_risk=False,
                ))
                break
 
    # ── LOW_CONFIDENCE — missing or very short ingredient list ──────────────────
    # is_safety_risk=True — unknown ingredient data means we cannot verify safety.
    if not ingredients_text or not ingredients_text.strip():
        signals.append(CautionSignal(
            "LOW_CONFIDENCE",
            "Ingredient list is missing for this product — unable to check "
            "for allergens, diet compatibility, or additives. "
            "Check the physical label before consuming.",
            12,
            is_safety_risk=True,
        ))
    elif len(parsed_ingredients) < _MIN_INGREDIENTS_FOR_CONFIDENCE:
        signals.append(CautionSignal(
            "LOW_CONFIDENCE",
            f"Ingredient list is unusually short "
            f"({len(parsed_ingredients)} item(s)) — the product database may "
            f"have incomplete data. Check the physical label.",
            8,
            is_safety_risk=True,
        ))
 
    return signals
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# 9.  TOP-LEVEL ANALYSIS FUNCTION
# ═══════════════════════════════════════════════════════════════════════════════
 
@dataclass
class RiskReport:
    """
    Full risk analysis result for a single product.
 
    Frontend reads: verdict, explanation
    Backend keeps:  hard_stops, caution_signals, caution_score (for tuning)
    """
    verdict:            str                  # OK | CAUTION | DONT_BUY
    explanation:        list[str]            # ordered bullet strings
    is_recalled:        bool
 
    hard_stops:         list[HardStop]
    caution_score:      int                  # non-additive point total (debug/tuning)
    caution_signals:    list[CautionSignal]
 
    allergen_matches:   list[AllergenMatch]
    diet_flags:         list[DietFlag]
    parsed_ingredients: list[str]
 
    def to_dict(self) -> dict:
        return {
            "verdict":            self.verdict,
            "explanation":        self.explanation,
            "is_recalled":        self.is_recalled,
            "hard_stops":         [asdict(h) for h in self.hard_stops],
            "caution_signals":    [
                {
                    "category":       s.category,
                    "detail":         s.detail,
                    "points":         s.points,
                    "is_safety_risk": s.is_safety_risk,
                }
                for s in self.caution_signals
            ],
            "allergen_count":     len(self.allergen_matches),
            "allergen_matches":   [m.to_dict() for m in self.allergen_matches],
            "diet_flag_count":    len(self.diet_flags),
            "diet_flags":         [f.to_dict() for f in self.diet_flags],
            "parsed_ingredients": self.parsed_ingredients,
            "_caution_score":     self.caution_score,
        }
 
 
def analyse_product_risk(
    ingredients_text: str,
    user_allergens: Optional[list[str]] = None,
    user_diets: Optional[list[str]] = None,
    is_recalled: bool = False,
    recall_date: Optional[str] = None,
    enable_llm: bool = False,
) -> RiskReport:
    """
    Full risk analysis for a single product.
 
    Pipeline:
      1. parse_ingredients()         — tokenise raw label text
      2. detect_allergens()          — 3-pass deterministic match
      3. check_diet_compatibility()  — deterministic rule check
      4. disambiguate_ingredients()  — LLM pass (only if enable_llm=True)
      5. _evaluate_hard_stops()      — Layer 1 binary gates
      6. _evaluate_caution_signals() — Layer 2 soft signals (skipped if stop)
      7. Determine verdict
      8. Build explanation bullets
 
    Verdict determination (Layer 2):
      • Any ADDITIVE signal present                           → CAUTION
        (bypasses threshold — any single additive is sufficient)
      • No ADDITIVE but non-additive score ≥ CAUTION_THRESHOLD → CAUTION
      • Otherwise                                            → OK
 
    Parameters
    ----------
    ingredients_text : str
        Raw ingredient string from the product / Open Food Facts.
    user_allergens : list[str], optional
        Canonical allergen names the user has declared.
    user_diets : list[str], optional
        Diet names the user follows.
    is_recalled : bool
        Whether the product currently has an active recall.
    recall_date : str, optional
        Date string of the recall (for the explanation bullet).
    enable_llm : bool
        If True, run the LLM disambiguator on ambiguous tokens via Bedrock.
        LLM HIGH confidence → PROBABLE (triggers hard stop).
        LLM MEDIUM confidence → POSSIBLE (soft caution only).
        LLM LOW/UNKNOWN → not added.
        If Bedrock is unavailable → returns [] → pipeline continues.
 
    Returns
    -------
    RiskReport with verdict, explanation bullets, and full structured detail.
    """
    user_allergens = user_allergens or []
    user_diets = user_diets or []
    strict = frozenset(d for d in user_diets if d in _STRICT_DIETS)
 
    # ── Steps 1–3: Deterministic detection ────────────────────────────────────
    parsed = parse_ingredients(ingredients_text)
    allergen_matches = detect_allergens(ingredients_text, user_allergens)
    diet_flags = check_diet_compatibility(ingredients_text, user_diets)
 
    # ── Step 4: LLM disambiguation (optional, ?enable_ai=true) ───────────────
    if enable_llm and _LLM_AVAILABLE and (user_allergens or user_diets):
        try:
            llm_results = disambiguate_ingredients(
                parsed_tokens=parsed,
                full_ingredients_text=ingredients_text,
                user_allergens=user_allergens,
                user_diets=user_diets,
                allergen_synonyms=ALLERGEN_SYNONYMS,
                diet_rules=DIET_RULES,
            )
            for dr in llm_results:
                for allergen_name in dr.likely_allergens:
                    if not any(a.lower() == allergen_name.lower() for a in user_allergens):
                        continue
                    severity = (
                        Severity.HIGH if allergen_name in _HIGH_SEVERITY_ALLERGENS
                        else Severity.MEDIUM
                    )
                    if dr.allergen_confidence == "HIGH":
                        allergen_matches.append(AllergenMatch(
                            allergen=allergen_name,
                            matched_token=f"{dr.token} (AI-analysed)",
                            confidence=Confidence.PROBABLE,
                            severity=severity,
                        ))
                    elif dr.allergen_confidence == "MEDIUM":
                        allergen_matches.append(AllergenMatch(
                            allergen=allergen_name,
                            matched_token=f"{dr.token} (AI-analysed)",
                            confidence=Confidence.POSSIBLE,
                            severity=severity,
                            is_advisory=True,
                        ))
        except ImportError:
            log.warning("LLM_services not available — skipping disambiguation.")
        except Exception as exc:
            log.warning("LLM disambiguation failed — continuing deterministic: %s", exc)
 
    # ── Step 5: Layer 1 — Hard stops ──────────────────────────────────────────
    hard_stops = _evaluate_hard_stops(
        is_recalled=is_recalled,
        recall_date=recall_date,
        allergen_matches=allergen_matches,
        diet_flags=diet_flags,
        strict_diets=strict,
    )
 
    if hard_stops:
        verdict = Verdict.DONT_BUY
        caution_signals: list[CautionSignal] = []
        caution_score = 0
    else:
        # ── Step 6: Layer 2 — Soft caution signals ────────────────────────────
        caution_signals = _evaluate_caution_signals(
            allergen_matches=allergen_matches,
            diet_flags=diet_flags,
            parsed_ingredients=parsed,
            strict_diets=strict,
            ingredients_text=ingredients_text,
        )
 
        # ── Step 7: Determine verdict ──────────────────────────────────────────
        # ADDITIVE signals bypass the point threshold — any single additive
        # is sufficient to return CAUTION. Non-additive signals (DIET_SOFT,
        # LOW_CONFIDENCE, CROSS_CONTACT) still accumulate toward the threshold.
        has_additive_signal = any(s.category == "ADDITIVE" for s in caution_signals)
        non_additive_score = sum(
            s.points for s in caution_signals if s.category != "ADDITIVE"
        )
        # caution_score kept as total for debugging and future tuning
        caution_score = sum(s.points for s in caution_signals)
 
        verdict = Verdict.CAUTION if (
            has_additive_signal or non_additive_score >= CAUTION_THRESHOLD
        ) else Verdict.OK
 
    # ── Step 8: Build explanation bullets ─────────────────────────────────────
    explanation: list[str] = []
    for h in hard_stops:
        explanation.append(h.reason)
    for s in caution_signals:
        explanation.append(s.detail)
    if not explanation:
        explanation.append("No issues detected — product appears safe for your profile.")
 
    return RiskReport(
        verdict=verdict.value,
        explanation=explanation,
        is_recalled=is_recalled,
        hard_stops=hard_stops,
        caution_score=caution_score,
        caution_signals=caution_signals,
        allergen_matches=allergen_matches,
        diet_flags=diet_flags,
        parsed_ingredients=parsed,
    )