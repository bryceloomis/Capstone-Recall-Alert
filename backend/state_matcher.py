"""
state_matcher.py – Parse FDA recall distribution_pattern text and determine
whether a given US state is affected.

The distribution_pattern field is free-text from the FDA enforcement API.
Examples:
  - "Nationwide"
  - "Distributors in 6 states: NY, VA, TX, GA, FL and MA"
  - "Nationwide, including Puerto Rico, Virgin Islands, Canada, and Japan"
  - "Products were distributed directly to specialized dental clinics in
     California and Arizona"
  - "Distributed in the Mid-Atlantic region (PA, NJ, DE)."
  - "Sold online through company website."

Strategy:
  1. Detect "nationwide" / "all states" / online distribution → all states match.
  2. Extract explicit 2-letter state abbreviations (e.g. "NY", "CA").
  3. Extract full state names (e.g. "California", "New York").
  4. Expand region names (e.g. "Midwest", "New England") into constituent states.
  5. If we can't extract ANY geographic signal, assume nationwide (fail-open)
     so that users don't miss potentially relevant recalls.
"""

import re
from typing import Optional

# ── State name ↔ abbreviation mappings ────────────────────────────────────────

STATE_ABBR_TO_NAME: dict[str, str] = {
    "AL": "Alabama",       "AK": "Alaska",        "AZ": "Arizona",
    "AR": "Arkansas",      "CA": "California",     "CO": "Colorado",
    "CT": "Connecticut",   "DE": "Delaware",       "FL": "Florida",
    "GA": "Georgia",       "HI": "Hawaii",         "ID": "Idaho",
    "IL": "Illinois",      "IN": "Indiana",        "IA": "Iowa",
    "KS": "Kansas",        "KY": "Kentucky",       "LA": "Louisiana",
    "ME": "Maine",         "MD": "Maryland",       "MA": "Massachusetts",
    "MI": "Michigan",      "MN": "Minnesota",      "MS": "Mississippi",
    "MO": "Missouri",      "MT": "Montana",        "NE": "Nebraska",
    "NV": "Nevada",        "NH": "New Hampshire",  "NJ": "New Jersey",
    "NM": "New Mexico",    "NY": "New York",       "NC": "North Carolina",
    "ND": "North Dakota",  "OH": "Ohio",           "OK": "Oklahoma",
    "OR": "Oregon",        "PA": "Pennsylvania",   "RI": "Rhode Island",
    "SC": "South Carolina","SD": "South Dakota",   "TN": "Tennessee",
    "TX": "Texas",         "UT": "Utah",           "VT": "Vermont",
    "VA": "Virginia",      "WA": "Washington",     "WV": "West Virginia",
    "WI": "Wisconsin",     "WY": "Wyoming",
    "DC": "District of Columbia",
    # Territories
    "PR": "Puerto Rico",   "VI": "Virgin Islands", "GU": "Guam",
    "AS": "American Samoa","MP": "Northern Mariana Islands",
}

STATE_NAME_TO_ABBR: dict[str, str] = {
    name.lower(): abbr for abbr, name in STATE_ABBR_TO_NAME.items()
}

ALL_STATE_ABBRS = set(STATE_ABBR_TO_NAME.keys())

# ── Region → state mappings ───────────────────────────────────────────────────

REGION_TO_STATES: dict[str, set[str]] = {
    "new england": {"CT", "ME", "MA", "NH", "RI", "VT"},
    "mid-atlantic": {"NJ", "NY", "PA"},
    "mid atlantic": {"NJ", "NY", "PA"},
    "midatlantic": {"NJ", "NY", "PA"},
    "northeast": {"CT", "ME", "MA", "NH", "RI", "VT", "NJ", "NY", "PA"},
    "southeast": {"AL", "AR", "FL", "GA", "KY", "LA", "MS", "NC", "SC", "TN", "VA", "WV"},
    "south": {"AL", "AR", "FL", "GA", "KY", "LA", "MS", "NC", "SC", "TN", "TX", "VA", "WV", "OK"},
    "southwest": {"AZ", "NM", "OK", "TX"},
    "midwest": {"IL", "IN", "IA", "KS", "MI", "MN", "MO", "NE", "ND", "OH", "SD", "WI"},
    "great plains": {"KS", "NE", "ND", "SD"},
    "mountain": {"CO", "ID", "MT", "NV", "UT", "WY"},
    "mountain west": {"CO", "ID", "MT", "NV", "UT", "WY"},
    "pacific": {"AK", "CA", "HI", "OR", "WA"},
    "pacific northwest": {"OR", "WA"},
    "west coast": {"CA", "OR", "WA"},
    "east coast": {"CT", "DE", "FL", "GA", "ME", "MD", "MA", "NH", "NJ", "NY",
                   "NC", "PA", "RI", "SC", "VA", "VT", "DC"},
    "gulf coast": {"AL", "FL", "LA", "MS", "TX"},
    "gulf states": {"AL", "FL", "LA", "MS", "TX"},
    "great lakes": {"IL", "IN", "MI", "MN", "NY", "OH", "PA", "WI"},
    "tri-state": {"NY", "NJ", "CT"},
    "tristate": {"NY", "NJ", "CT"},
    "four corners": {"AZ", "CO", "NM", "UT"},
}

# ── Nationwide detection patterns ─────────────────────────────────────────────

_NATIONWIDE_PATTERNS = [
    r"\bnationwide\b",
    r"\ball\s+50\s+states\b",
    r"\ball\s+states\b",
    r"\bthroughout\s+the\s+united\s+states\b",
    r"\bthroughout\s+the\s+u\.?s\.?\b",
    r"\bacross\s+the\s+u\.?s\.?\b",
    r"\bacross\s+the\s+united\s+states\b",
    r"\bdomestic\s+distribution\b",
    r"\bu\.?s\.?\s*wide\b",
    r"\bcountrywide\b",
    r"\bsold\s+online\b",
    r"\bvia\s+(the\s+)?internet\b",
    r"\bonline\s+(through|via|at)\b",
    r"\be-?commerce\b",
    r"\bwebsite\s+sales?\b",
    r"\bmail\s+order\b",
    r"\bamazon\.com\b",
    r"\bwalmart\b",
    r"\bcostco\b",
    r"\btarget\b",
    r"\bwhole\s+foods\b",
    r"\bkroger\b",
]

_NATIONWIDE_RE = re.compile("|".join(_NATIONWIDE_PATTERNS), re.IGNORECASE)

# ── Abbreviation extraction regex ─────────────────────────────────────────────
# Match 2-letter uppercase sequences that are valid state abbreviations.
# Use word boundaries to avoid matching random uppercase pairs in words.
_ABBR_RE = re.compile(r"\b([A-Z]{2})\b")

# ── Full state name regex (built once) ────────────────────────────────────────
# Sort by length descending so "New Hampshire" matches before "New" accidentally
_sorted_names = sorted(STATE_NAME_TO_ABBR.keys(), key=len, reverse=True)
_STATE_NAME_RE = re.compile(
    r"\b(" + "|".join(re.escape(n) for n in _sorted_names) + r")\b",
    re.IGNORECASE,
)

# ── Region name regex (built once) ────────────────────────────────────────────
_sorted_regions = sorted(REGION_TO_STATES.keys(), key=len, reverse=True)
_REGION_RE = re.compile(
    r"\b(" + "|".join(re.escape(r) for r in _sorted_regions) + r")\b",
    re.IGNORECASE,
)


def extract_states(distribution_pattern: Optional[str]) -> tuple[set[str], bool]:
    """
    Parse a distribution_pattern string and extract affected US states.

    Returns:
        (states, is_nationwide)
        - states: set of 2-letter state abbreviations found in the text
        - is_nationwide: True if the recall applies to the entire US

    If is_nationwide is True, `states` will contain ALL state abbreviations.
    If we cannot extract any geographic info, we treat it as nationwide
    (fail-open to avoid missing relevant recalls).
    """
    if not distribution_pattern or not distribution_pattern.strip():
        return (set(ALL_STATE_ABBRS), True)  # No data → assume nationwide

    text = distribution_pattern.strip()
    found_states: set[str] = set()
    is_nationwide = False

    # 1. Check for nationwide keywords
    if _NATIONWIDE_RE.search(text):
        is_nationwide = True
        found_states = set(ALL_STATE_ABBRS)
        return (found_states, is_nationwide)

    # 2. Extract 2-letter state abbreviations
    for match in _ABBR_RE.finditer(text):
        abbr = match.group(1)
        if abbr in ALL_STATE_ABBRS:
            found_states.add(abbr)

    # 3. Extract full state names
    for match in _STATE_NAME_RE.finditer(text):
        name = match.group(1).lower()
        abbr = STATE_NAME_TO_ABBR.get(name)
        if abbr:
            found_states.add(abbr)

    # 4. Expand region names
    for match in _REGION_RE.finditer(text):
        region = match.group(1).lower()
        region_states = REGION_TO_STATES.get(region)
        if region_states:
            found_states.update(region_states)

    # 5. Fail-open: if no geographic signal found, assume nationwide
    if not found_states:
        return (set(ALL_STATE_ABBRS), True)

    return (found_states, False)


def is_state_affected(user_state: Optional[str], distribution_pattern: Optional[str]) -> bool:
    """
    Determine whether a user's state is affected by a recall's distribution.

    Args:
        user_state: 2-letter state abbreviation (e.g. "CA") or None
        distribution_pattern: Free-text FDA distribution field

    Returns:
        True if the user's state is in the recall's distribution area.
        Also returns True if user_state is None (can't filter without a state).
    """
    if not user_state:
        return True  # No state on file → show all recalls

    user_state = user_state.strip().upper()
    if user_state not in ALL_STATE_ABBRS:
        return True  # Invalid state → fail-open

    states, _ = extract_states(distribution_pattern)
    return user_state in states
