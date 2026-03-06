"""
ingredient_risk_engine.py – Deterministic ingredient risk scoring engine.

Provides three independent risk assessments on a per-product basis:

  1. ALLERGEN DETECTION
     Maps the user's declared allergens against the product ingredient list
     using a comprehensive synonym database covering the FDA "Big 9" allergens
     plus several extended categories.  Each allergen match carries a
     confidence score (DEFINITE / PROBABLE / POSSIBLE) based on *how* it was
     matched — exact token hit vs. derivative keyword vs. "may contain" /
     cross-contamination advisory language.

  2. DIET INCOMPATIBILITY
     Evaluates the ingredient list against rule sets for common dietary
     patterns (Vegan, Vegetarian, Gluten-Free, Kosher, Halal, Keto,
     Dairy-Free, Paleo).  Each flagged ingredient specifies *why* it is
     incompatible and its confidence level.

  3. COMPOSITE RISK SCORE
     A 0-100 score that blends recall status (if any), allergen severity,
     and diet incompatibility count into a single headline number the
     frontend can use for colour-coding (green / yellow / red).

All matching is deterministic — no ML model required.  Accuracy comes from
the breadth of the synonym dictionaries and the multi-pass parsing strategy
(exact → stem → substring → advisory-phrase).

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

from LLM_services import disambiguate_ingredients, DisambiguationResult, explain_recall

log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# 1.  CONSTANTS & ENUMS
# ═══════════════════════════════════════════════════════════════════════════════

class Confidence(str, Enum):
    DEFINITE = "DEFINITE"    # exact ingredient token match
    PROBABLE = "PROBABLE"    # derivative / scientific synonym match
    POSSIBLE = "POSSIBLE"    # advisory language ("may contain", "shared facility")


class Severity(str, Enum):
    HIGH   = "HIGH"          # life-threatening potential (anaphylaxis allergens)
    MEDIUM = "MEDIUM"        # significant but rarely life-threatening
    LOW    = "LOW"           # mild intolerance or preference-based


# Allergens that commonly cause anaphylaxis → HIGH severity by default.
_HIGH_SEVERITY_ALLERGENS = frozenset({
    "Milk", "Eggs", "Peanuts", "Tree Nuts", "Fish",
    "Shellfish", "Wheat", "Soy", "Sesame",
})


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
        "galactose",
        "recaldent",
        "rennet casein",
        "tagatose",
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
        "abalone",
        "cockle",
        "cuttlefish",
        "limpet",
        "octopus",
        "sea urchin", "uni",
        "chitosan",     # derived from crustacean shells
        "glucosamine",  # often from shellfish
    },

    "Wheat": {
        "wheat", "wheat flour", "whole wheat", "wheat starch",
        "wheat bran", "wheat germ", "wheat gluten", "wheat grass",
        "wheat protein", "hydrolysed wheat protein",
        "bread crumbs", "breadcrumbs",
        "bulgur",
        "couscous",
        "cracker meal",
        "durum", "durum flour",
        "einkorn",
        "emmer",
        "farina",
        "flour",   # unqualified "flour" is almost always wheat
        "freekeh",
        "graham flour",
        "kamut", "khorasan",
        "matzoh", "matzo", "matzah",
        "orzo",   # wheat pasta
        "pasta",  # default pasta = wheat
        "seitan",
        "semolina",
        "spelt",
        "triticale",
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
        "edamame",
        "miso",
        "natto",
        "tempeh",
        "textured vegetable protein", "tvp",
        "tofu", "bean curd",
        "hydrolysed soy protein",
        "soy albumin",
        "soy fiber", "soy fibre",
        "soy grits",
        "soy nuts",
    },

    "Sesame": {
        "sesame", "sesame seed", "sesame seeds",
        "sesame oil", "sesame paste", "sesame flour",
        "tahini", "tahina",
        "halvah", "halva",
        "hummus",   # traditionally contains tahini
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
        "triticale",
        "spelt", "kamut", "einkorn", "emmer", "farro",
        "seitan",
        "brewer's yeast",    # often contains gluten
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
        "celery", "celery seed", "celery salt", "celery powder",
        "celeriac",
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
            "carmine", "cochineal",    # red dye from insects
            "shellac", "confectioner's glaze",
            "isinglass",               # from fish swim bladders
            "rennet",
            "vitamin d3",              # often from lanolin
            "omega-3",                 # often from fish oil
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
            "rennet",       # animal rennet (microbial is OK)
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

    Returns lowercase, stripped tokens.
    """
    if not raw:
        return []

    text = raw.strip()

    # Strip common prefixes
    text = re.sub(r"^(?:ingredients?\s*:?\s*)", "", text, flags=re.I)

    # Flatten parenthetical sub-ingredients into separate tokens
    # e.g. "chocolate (sugar, cocoa butter)" → "chocolate, sugar, cocoa butter"
    text = re.sub(r"\(([^)]*)\)", lambda m: ", " + m.group(1), text)

    # Normalise delimiters
    text = text.replace("|", ",").replace(";", ",")

    # Remove percentage annotations
    text = re.sub(r"\d+(\.\d+)?\s*%", "", text)

    # Split, strip, lowercase, deduplicate while preserving order
    seen: set[str] = set()
    tokens: list[str] = []
    for chunk in text.split(","):
        t = chunk.strip().strip(".").strip(":").lower()
        t = re.sub(r"\s+", " ", t)          # collapse whitespace
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
            # Split the fragment (e.g. "milk, eggs, and tree nuts")
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
    matched_token:   str              # the ingredient token that triggered the match
    confidence:      Confidence
    severity:        Severity
    is_advisory:     bool = False     # from "may contain" language

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
      Pass 2 — substring containment (catches compound terms)  → PROBABLE
      Pass 3 — advisory phrase extraction                      → POSSIBLE

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
            # Try case-insensitive lookup
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

        # ── Pass 1: exact token match ─────────────────────────────────────
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

        # ── Pass 2: substring / partial match ─────────────────────────────
        #     Catches cases like "contains milk protein" where "milk protein"
        #     isn't in the synonym set but "milk" is.
        for synonym in synonyms:
            if len(synonym) < 3:
                continue  # skip tiny tokens to avoid false positives
            for token in tokens:
                if synonym in token and (allergen_name, token) not in matches:
                    matches[(allergen_name, token)] = AllergenMatch(
                        allergen=allergen_name,
                        matched_token=token,
                        confidence=Confidence.PROBABLE,
                        severity=severity,
                    )

        # ── Pass 3: advisory / "may contain" phrases ──────────────────────
        advisory_tokens = _extract_advisory_allergens(raw_lower)
        for adv_token in advisory_tokens:
            if adv_token in synonyms or any(s in adv_token for s in synonyms if len(s) >= 3):
                key = (allergen_name, f"advisory:{adv_token}")
                if key not in matches:
                    matches[key] = AllergenMatch(
                        allergen=allergen_name,
                        matched_token=adv_token,
                        confidence=Confidence.POSSIBLE,
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
            # Case-insensitive fallback
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
            # Exact match
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

            # Substring match (catches multi-word forbidden items)
            for forbidden_item in forbidden:
                if len(forbidden_item) >= 3 and forbidden_item in token:
                    key = (diet_name, token)
                    if key not in seen:
                        seen.add(key)
                        flags.append(DietFlag(
                            diet=diet_name,
                            flagged_token=token,
                            reason=f"'{token}' likely contains '{forbidden_item}', incompatible with {diet_name}",
                            confidence=Confidence.PROBABLE,
                        ))
                    break

    return flags


# ═══════════════════════════════════════════════════════════════════════════════
# 8.  TWO-LAYER VERDICT SYSTEM
# ═══════════════════════════════════════════════════════════════════════════════
#
#   Layer 1 – HARD STOPS (binary gates)
#     If ANY hard stop fires → verdict = DONT_BUY.
#       • Active FDA recall
#       • DEFINITE or PROBABLE match on a user-declared allergen
#       • DEFINITE violation of a strict diet preference
#
#   Layer 2 – SOFT CAUTION SIGNALS (point-based)
#     Only evaluated when no hard stop fires.
#       • Cross-contact / advisory allergen mentions
#       • PROBABLE diet flags, or DEFINITE on non-strict diets
#       • Known controversial additives
#       • Missing or very short ingredient list
#     If caution_score >= threshold → CAUTION, else → OK
#
#   The numeric caution_score is kept for internal tuning but the API
#   exposes only the three-way verdict + explanation bullets.
# ═══════════════════════════════════════════════════════════════════════════════

class Verdict(str, Enum):
    OK       = "OK"
    CAUTION  = "CAUTION"
    DONT_BUY = "DONT_BUY"


# Diets treated as strict (medical / ethical non-negotiables) by default.
# Non-strict diets (Keto, Paleo) produce caution signals, not hard stops.
_STRICT_DIETS = frozenset({
    "Gluten-Free", "Dairy-Free", "Vegan", "Vegetarian", "Halal", "Kosher",
})

# Threshold above which soft signals flip the verdict to CAUTION.
CAUTION_THRESHOLD = 15


# ── Known controversial additives ─────────────────────────────────────────────

FLAGGED_ADDITIVES: dict[str, tuple[str, int]] = {
    "high fructose corn syrup": ("Linked to metabolic concerns", 6),
    "hfcs":                     ("High fructose corn syrup", 6),
    "aspartame":                ("Artificial sweetener; some individuals sensitive", 4),
    "sucralose":                ("Artificial sweetener", 3),
    "acesulfame potassium":     ("Artificial sweetener (Ace-K)", 3),
    "acesulfame k":             ("Artificial sweetener (Ace-K)", 3),
    "sodium nitrite":           ("Preservative in processed meats", 5),
    "sodium nitrate":           ("Preservative in processed meats", 5),
    "bha":                      ("Synthetic antioxidant preservative", 4),
    "bht":                      ("Synthetic antioxidant preservative", 4),
    "tbhq":                     ("Synthetic preservative", 4),
    "monosodium glutamate":     ("MSG; some individuals report sensitivity", 3),
    "msg":                      ("Monosodium glutamate", 3),
    "carrageenan":              ("Thickener; debated GI effects", 3),
    "sodium benzoate":          ("Preservative; may form benzene with vitamin C", 4),
    "potassium bromate":        ("Flour improver; banned in many countries", 6),
    "propylparaben":            ("Preservative; endocrine disruptor concerns", 5),
    "titanium dioxide":         ("Colour additive; banned in EU food since 2022", 5),
    "red 40":                   ("Synthetic dye; linked to hyperactivity", 4),
    "red dye 40":               ("Synthetic dye; linked to hyperactivity", 4),
    "yellow 5":                 ("Synthetic dye (tartrazine)", 4),
    "yellow 6":                 ("Synthetic dye (sunset yellow)", 4),
    "blue 1":                   ("Synthetic dye (brilliant blue)", 3),
    "partially hydrogenated":   ("Source of artificial trans fats", 6),
    "hydrogenated oil":         ("May contain trans fats", 5),
}

_MIN_INGREDIENTS_FOR_CONFIDENCE = 2


# ── Layer 1: Hard stops ───────────────────────────────────────────────────────

@dataclass
class HardStop:
    gate:   str   # RECALL | ALLERGEN | DIET_STRICT
    reason: str   # human-readable explanation bullet


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
        stops.append(HardStop("RECALL", f"Active FDA recall reported{date_part}"))

    # Gate 2: confirmed allergen (DEFINITE or PROBABLE, not advisory-only)
    seen_allergens: set[str] = set()
    for m in allergen_matches:
        if m.confidence in (Confidence.DEFINITE, Confidence.PROBABLE) and m.allergen not in seen_allergens:
            seen_allergens.add(m.allergen)
            verb = "Contains" if m.confidence == Confidence.DEFINITE else "Likely contains"
            stops.append(HardStop(
                "ALLERGEN",
                f"{verb} {m.allergen.lower()} (your allergen) — detected '{m.matched_token}'",
            ))

    # Gate 3: strict diet violation (DEFINITE only)
    seen_diets: set[str] = set()
    for f in diet_flags:
        if f.confidence == Confidence.DEFINITE and f.diet in strict_diets and f.diet not in seen_diets:
            seen_diets.add(f.diet)
            stops.append(HardStop(
                "DIET_STRICT",
                f"Violates {f.diet} diet — contains '{f.flagged_token}'",
            ))

    return stops


# ── Layer 2: Soft caution signals ─────────────────────────────────────────────

@dataclass
class CautionSignal:
    category: str   # CROSS_CONTACT | ADDITIVE | DIET_SOFT | LOW_CONFIDENCE | AMBIGUOUS
    detail:   str   # human-readable explanation bullet
    points:   int


def _evaluate_caution_signals(
    allergen_matches: list[AllergenMatch],
    diet_flags: list[DietFlag],
    parsed_ingredients: list[str],
    strict_diets: frozenset[str],
    ingredients_text: str,
) -> list[CautionSignal]:
    signals: list[CautionSignal] = []

    # Cross-contact / advisory allergen mentions (POSSIBLE confidence)
    seen: set[str] = set()
    for m in allergen_matches:
        if m.confidence == Confidence.POSSIBLE and m.allergen not in seen:
            seen.add(m.allergen)
            signals.append(CautionSignal(
                "CROSS_CONTACT",
                f"May contain {m.allergen.lower()} (cross-contact advisory)",
                8,
            ))

    # Non-strict or PROBABLE diet flags
    seen_dt: set[tuple[str, str]] = set()
    for f in diet_flags:
        key = (f.diet, f.flagged_token)
        if key in seen_dt:
            continue
        seen_dt.add(key)
        if f.confidence == Confidence.PROBABLE:
            signals.append(CautionSignal(
                "DIET_SOFT",
                f"Likely incompatible with {f.diet} — '{f.flagged_token}'",
                5,
            ))
        elif f.confidence == Confidence.DEFINITE and f.diet not in strict_diets:
            signals.append(CautionSignal(
                "DIET_SOFT",
                f"Incompatible with {f.diet} preference — '{f.flagged_token}'",
                4,
            ))

    # Known controversial additives
    for token in parsed_ingredients:
        entry = FLAGGED_ADDITIVES.get(token)
        if entry:
            desc, pts = entry
            signals.append(CautionSignal("ADDITIVE", f"Contains '{token}' — {desc}", pts))
        else:
            for additive_key, (desc, pts) in FLAGGED_ADDITIVES.items():
                if len(additive_key) >= 5 and additive_key in token:
                    signals.append(CautionSignal("ADDITIVE", f"Contains '{token}' — {desc}", pts))
                    break

    # Missing or very short ingredient list
    if not ingredients_text or not ingredients_text.strip():
        signals.append(CautionSignal(
            "LOW_CONFIDENCE",
            "Ingredient list missing — unable to perform full analysis",
            12,
        ))
    elif len(parsed_ingredients) < _MIN_INGREDIENTS_FOR_CONFIDENCE:
        signals.append(CautionSignal(
            "LOW_CONFIDENCE",
            f"Ingredient list very short ({len(parsed_ingredients)} item(s)) — low confidence",
            8,
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
    Backend keeps:  hard_stops, caution_signals, _caution_score (for tuning)
    """
    verdict:            str                  # OK | CAUTION | DONT_BUY
    explanation:        list[str]            # ordered bullet strings
    is_recalled:        bool

    hard_stops:         list[HardStop]
    caution_score:      int
    caution_signals:    list[CautionSignal]

    allergen_matches:   list[AllergenMatch]
    diet_flags:         list[DietFlag]
    parsed_ingredients: list[str]

    def to_dict(self) -> dict:
        return {
            "verdict":          self.verdict,
            "explanation":      self.explanation,
            "is_recalled":      self.is_recalled,
            "hard_stops":       [asdict(h) for h in self.hard_stops],
            "caution_signals":  [asdict(s) for s in self.caution_signals],
            "allergen_count":   len(self.allergen_matches),
            "allergen_matches": [m.to_dict() for m in self.allergen_matches],
            "diet_flag_count":  len(self.diet_flags),
            "diet_flags":       [f.to_dict() for f in self.diet_flags],
            "parsed_ingredients": self.parsed_ingredients,
            "_caution_score":   self.caution_score,
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
      1. parse_ingredients()           — tokenise raw label text
      2. detect_allergens()            — deterministic 3-pass match
      3. check_diet_compatibility()    — deterministic rule check
      4. disambiguate_ingredients()    — LLM pass (only if enable_llm=True)
         See llm_service.py for full documentation.
      5. _evaluate_hard_stops()        — Layer 1 binary gates
      6. _evaluate_caution_signals()   — Layer 2 soft scoring
      7. Build explanation bullets

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
        If True, run the LLM disambiguator on ambiguous tokens.

    Returns
    -------
    RiskReport with verdict, explanation bullets, and full detail.
    """
    user_allergens = user_allergens or []
    user_diets = user_diets or []
    strict = frozenset(d for d in user_diets if d in _STRICT_DIETS)

    # ── Steps 1-3: Deterministic detection ────────────────────────────────
    parsed = parse_ingredients(ingredients_text)
    allergen_matches = detect_allergens(ingredients_text, user_allergens)
    diet_flags = check_diet_compatibility(ingredients_text, user_diets)

    # ── Step 4: LLM disambiguation (optional) ────────────────────────────
    #
    #   Called AFTER deterministic passes, BEFORE verdict evaluation.
    #   Merges extra AllergenMatch objects into the existing list so the
    #   hard-stop evaluation sees them.
    #
    #   LLM HIGH confidence → PROBABLE (can trigger hard stop)
    #   LLM MEDIUM confidence → POSSIBLE advisory (caution signal only)
    #   LLM LOW/UNKNOWN → not added
    #
    #   If Bedrock is unavailable → returns [] → pipeline continues.
    #
    llm_results = []
    if enable_llm and (user_allergens or user_diets):
        try:
            #from llm_service import disambiguate_ingredients, DisambiguationResult

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
            log.warning("llm_service module not available — skipping disambiguation.")
        except Exception as exc:
            log.warning("LLM disambiguation failed — continuing deterministic: %s", exc)

    # ── Step 5: Layer 1 — Hard stops ──────────────────────────────────────
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
        # ── Step 6: Layer 2 — Soft caution signals ────────────────────────
        caution_signals = _evaluate_caution_signals(
            allergen_matches=allergen_matches,
            diet_flags=diet_flags,
            parsed_ingredients=parsed,
            strict_diets=strict,
            ingredients_text=ingredients_text,
        )
        caution_score = sum(s.points for s in caution_signals)
        verdict = Verdict.CAUTION if caution_score >= CAUTION_THRESHOLD else Verdict.OK

    # ── Step 7: Build explanation bullets ──────────────────────────────────
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