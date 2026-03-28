"""
risk_routes.py – FastAPI APIRouter for ingredient risk analysis.
 
Endpoint:
  GET  /api/risk/scan/{upc}  – full scan: product lookup + risk analysis
                               (the main endpoint the mobile app calls
                                immediately after scanning a barcode)
 
Query params:
  ?user_id=42       personalise risk against this user's allergen/diet profile
  ?enable_ai=true   enable LLM ingredient disambiguation via AWS Bedrock Haiku
                    (only called when ambiguous tokens are present)
 
Response shape:
{
  "found": true,
  "product": { upc, product_name, brand_name, category, ingredients, image_url },
  "recall":  { ...raw recall row..., "summary": { headline, what_happened,
               action, who_is_at_risk, severity_plain, locations } } | null,
  "verdict": "DONT_BUY" | "CAUTION" | "OK",
  "explanation": ["bullet 1", "bullet 2", ...],
  "notifications": [
    {
      "type":          "RECALL" | "ALLERGEN" | "DIET" | "ADDITIVE" | "WARNING",
      "severity":      "HIGH" | "MEDIUM" | "LOW",
      "is_safety_risk": true | false,
      "title":         "short bold headline",
      "summary":       "one plain-English sentence",
      "cards":         [ { "label": "WHAT HAPPENED", "body": "..." }, ... ],
      "message":       "legacy flat text (all card bodies joined)"
    }
  ],
  "risk": { ...full RiskReport.to_dict()... }
}
 
Notification card structure per type
──────────────────────────────────────────────────────────────────────────────
RECALL           WHAT HAPPENED · WHO IS AT RISK · WHAT TO DO · RECALL CLASS
                 · WHERE RECALLED
                 Fallback when LLM unavailable: WHAT HAPPENED uses raw FDA
                 reason_for_recall; WHAT TO DO uses deterministic
                 _fallback_action(severity); WHERE RECALLED uses raw
                 distribution_pattern string.
 
ALLERGEN         Two variants based on is_advisory flag:
  Confirmed      ALLERGEN FOUND · YOUR ALLERGY · WHAT TO DO · RECALL STATUS
  Advisory       ADVISORY WARNING · YOUR ALLERGY · WHAT TO DO · RECALL STATUS
                 "May Contain" language now triggers DONT_BUY (same gate as
                 confirmed), but distinct card wording makes it clear the
                 allergen was found in an advisory statement, not the
                 ingredient list itself.
 
DIET (hard stop) DIET CONFLICT · NOT A SAFETY RISK · YOUR PREFERENCE
                 is_safety_risk = false — frontend can soften badge styling.
 
DIET (soft)      DIET CONFLICT · NOT A SAFETY RISK
                 is_safety_risk = false
 
ADDITIVE         ADDITIVE FLAG
                 is_safety_risk = false
 
WARNING          DATA GAP
                 is_safety_risk = true (unknown → conservative)
──────────────────────────────────────────────────────────────────────────────
 
State-based recall filtering
──────────────────────────────────────────────────────────────────────────────
check_recall() returns any matching recall without knowing the user's state.
After the recall is retrieved, _state_matches_distribution() (imported from
user_alerts, single source of truth) is used to suppress recalls whose
distribution_pattern does not cover the user's state.
 
Conservative rules:
  • Empty/null distribution → show to everyone (nationwide assumed)
  • user_state = None (unauthenticated or state not stored) → skip filter
──────────────────────────────────────────────────────────────────────────────
"""
 
from __future__ import annotations
 
import logging
from typing import Optional
 
from fastapi import APIRouter, HTTPException, Query
 
from database import execute_query
from ingredient_risk_engine import analyse_product_risk
from barcode_routes import _lookup_off, _cache_product, check_recall
 
log = logging.getLogger(__name__)
 
router = APIRouter(prefix="/api/risk", tags=["risk"])
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════════════════════════
 
def _load_user_profile(user_id: int) -> dict:
    """
    Fetch allergens, diet preferences, and state for a user from the DB.
 
    Returns {"allergens": [...], "diets": [...], "state": "CA" | None}.
 
    state is used for recall distribution filtering so a user in California
    does not get a DONT_BUY verdict for a recall whose distribution only
    covers Texas.
    """
    rows = execute_query(
        "SELECT allergens, diet_preferences, state FROM users WHERE id = %s LIMIT 1;",
        (user_id,),
    )
    if not rows:
        return {"allergens": [], "diets": [], "state": None}
    row = rows[0]
    allergens = row.get("allergens") or []
    diets     = row.get("diet_preferences") or []
    if isinstance(allergens, str):
        allergens = [a.strip() for a in allergens.split(",") if a.strip()]
    if isinstance(diets, str):
        diets = [d.strip() for d in diets.split(",") if d.strip()]
    return {"allergens": allergens, "diets": diets, "state": row.get("state")}
 
 
def _resolve_product(upc: str) -> Optional[dict]:
    """
    Look up a product by UPC.
 
    Checks the local DB cache first; falls back to Open Food Facts API.
    Caches the OFFs result for future lookups.
    Returns a product dict or None if not found.
    """
    rows = execute_query("SELECT * FROM products WHERE upc = %s LIMIT 1;", (upc,))
    if rows:
        return rows[0]
    off_data = _lookup_off(upc)
    if off_data:
        _cache_product(off_data)
        return off_data
    return None
 
 
def _load_recall_summary(recall_id: Optional[int]) -> Optional[dict]:
    """
    Load the LLM-generated plain-language summary for a recall from the DB.
 
    Stored in:  recalls.plain_language_summary  (JSONB column)
    Generated by: LLM_services.explain_recall() during the FDA refresh pipeline
    Keys: headline, what_happened, who_is_at_risk, action, severity_plain,
          locations, what_to_do (backward-compat alias for action)
 
    Returns None if the summary has not been generated yet (e.g. Bedrock was
    unavailable during the last refresh, or the recall was just ingested).
    _build_notifications() handles the None case by falling back to raw FDA text.
    """
    if not recall_id:
        return None
    try:
        rows = execute_query(
            "SELECT plain_language_summary FROM recalls WHERE id = %s LIMIT 1;",
            (recall_id,),
        )
        if rows and rows[0].get("plain_language_summary"):
            summary = rows[0]["plain_language_summary"]
            return summary if isinstance(summary, dict) else None
    except Exception:
        pass
    return None
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════
 
@router.get("/scan/{upc}")
async def scan_barcode_with_risk(
    upc: str,
    user_id: Optional[int] = Query(
        None, description="Logged-in user ID for personalised risk"
    ),
    enable_ai: bool = Query(
        False,
        description="Enable LLM disambiguation for ambiguous ingredients "
                    "(calls AWS Bedrock Haiku — only when ambiguous tokens present)",
    ),
):
    """
    Primary barcode-scan endpoint.
 
    Combines product lookup → recall check → state filtering → allergen
    detection → diet check into a single response. The frontend calls this
    immediately after the camera decodes a barcode.
    """
    # ── 1. Product lookup ────────────────────────────────────────────────────
    product = _resolve_product(upc)
    if not product:
        return {
            "found":         False,
            "upc":           upc,
            "message":       "Product not found. Please enter details manually.",
            "verdict":       None,
            "explanation":   [],
            "notifications": [],
            "risk":          None,
        }
 
    # ── 2. User profile ───────────────────────────────────────────────────────
    allergens:  list[str]     = []
    diets:      list[str]     = []
    user_state: Optional[str] = None
    if user_id:
        profile    = _load_user_profile(user_id)
        allergens  = profile["allergens"]
        diets      = profile["diets"]
        user_state = profile["state"]
 
    # ── 3. Recall check ───────────────────────────────────────────────────────
    recall_info = check_recall(
        upc,
        product_name=product.get("product_name") or "",
        brand_name=product.get("brand_name") or "",
    )
 
    # ── 4. State-based recall filtering ───────────────────────────────────────
    # Reuses _state_matches_distribution() from user_alerts — single source of
    # truth so live scan verdict is consistent with background alert generation.
    #
    # Conservative: empty/null distribution → show to everyone.
    #               user_state = None       → skip filter entirely.
    if recall_info and user_state:
        from user_alerts import _state_matches_distribution
        distribution = (
            recall_info.get("distribution")             # key set by format_recall
            or recall_info.get("distribution_pattern")  # raw DB column name
            or ""
        )
        if not _state_matches_distribution(user_state, distribution):
            log.debug(
                "Suppressing recall id=%s for user state=%s — "
                "distribution '%s' does not cover this state.",
                recall_info.get("id"), user_state, distribution,
            )
            recall_info = None   # treat as no recall for verdict + notifications
 
    # ── 5. Load LLM recall summary ────────────────────────────────────────────
    if recall_info:
        recall_info["summary"] = _load_recall_summary(recall_info.get("id"))
 
    # ── 6. Ingredient risk analysis ───────────────────────────────────────────
    ingredients_text = product.get("ingredients") or ""
 
    # Flat ingredient list for the product response (display only)
    ingredients_list = [
        i.strip()
        for i in ingredients_text.replace("|", ",").split(",")
        if i.strip()
    ]
 
    report = analyse_product_risk(
        ingredients_text=ingredients_text,
        user_allergens=allergens,
        user_diets=diets,
        is_recalled=(recall_info is not None),
        recall_date=recall_info.get("recall_date") if recall_info else None,
        enable_llm=enable_ai,
    )
 
    # ── 7. Build notifications ────────────────────────────────────────────────
    notifications = _build_notifications(
        report,
        recall_summary=(recall_info.get("summary") if recall_info else None),
        recall_severity=(recall_info.get("severity", "") if recall_info else ""),
        recall_distribution=(
            recall_info.get("distribution")
            or recall_info.get("distribution_pattern")
            or ""
        ) if recall_info else "",
        recall_reason=(recall_info.get("reason", "") if recall_info else ""),
    )
 
    return {
        "found":   True,
        "product": {
            "upc":          product.get("upc"),
            "product_name": product.get("product_name"),
            "brand_name":   product.get("brand_name") or "",
            "category":     product.get("category") or "Unknown",
            "ingredients":  ingredients_list,
            "image_url":    product.get("image_url") or "",
        },
        "recall":        recall_info,
        "verdict":       report.verdict,
        "explanation":   report.explanation,
        "notifications": notifications,
        "risk":          report.to_dict(),
    }
 
 
# ═══════════════════════════════════════════════════════════════════════════════
# NOTIFICATION BUILDER
# ═══════════════════════════════════════════════════════════════════════════════
 
# Maps hard-stop gate names → (notification_type, severity)
_GATE_TO_NOTIFICATION: dict[str, tuple[str, str]] = {
    "RECALL":      ("RECALL",   "HIGH"),
    "ALLERGEN":    ("ALLERGEN", "HIGH"),
    "DIET_STRICT": ("DIET",     "HIGH"),
}
 
# Maps caution-signal category → (notification_type, severity)
_CATEGORY_TO_NOTIFICATION: dict[str, tuple[str, str]] = {
    "CROSS_CONTACT":  ("ALLERGEN", "MEDIUM"),
    "DIET_SOFT":      ("DIET",     "MEDIUM"),
    "ADDITIVE":       ("ADDITIVE", "LOW"),
    "LOW_CONFIDENCE": ("WARNING",  "MEDIUM"),
    "AMBIGUOUS":      ("WARNING",  "LOW"),
}
 
 
def _build_notifications(
    report,
    recall_summary:      Optional[dict] = None,
    recall_severity:     str = "",
    recall_distribution: str = "",
    recall_reason:       str = "",
) -> list[dict]:
    """
    Convert a RiskReport into a typed notification list for the frontend.
 
    Each notification dict has:
      type          RECALL | ALLERGEN | DIET | ADDITIVE | WARNING
      severity      HIGH | MEDIUM | LOW
      is_safety_risk  False for diet-preference-only conflicts so the frontend
                      can soften badge styling without separate logic
      title         Short bold headline (≤6 words)
      summary       One plain-English sentence shown below the title
      cards         List of { label, body } sections rendered in the detail view
      message       Legacy flat string (all card bodies joined) for clients
                    that haven't adopted the card structure yet
 
    Parameters
    ----------
    report               : RiskReport returned by analyse_product_risk()
    recall_summary       : JSONB dict from recalls.plain_language_summary, or None.
                           Keys: headline, what_happened, who_is_at_risk, action,
                                 severity_plain, locations, what_to_do (legacy alias)
    recall_severity      : Raw FDA classification string, e.g. "Class I / Class 1"
    recall_distribution  : Raw distribution_pattern from the recalls table.
                           Fallback for WHERE RECALLED card when LLM-formatted
                           'locations' field is not yet in recall_summary.
    recall_reason        : Raw FDA reason_for_recall string.
                           Fallback for WHAT HAPPENED card when recall_summary
                           is None (Bedrock unavailable or record just ingested).
    """
    def _fallback_action(severity: str) -> str:
        s = (severity or "").lower()
        if "class i" in s or "class 1" in s:
            return "Do not eat, use, or sell this product. Return it to the store or dispose of it immediately."
        if "class ii" in s or "class 2" in s:
            return "Stop using this product. Return it to the store or follow the manufacturer's disposal instructions."
        return "Use caution. Check the FDA recall page for return or disposal instructions."

    notifications: list[dict] = []
 
    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 1: Hard stops → notifications
    # ─────────────────────────────────────────────────────────────────────────
    for h in report.hard_stops:
        ntype, severity = _GATE_TO_NOTIFICATION.get(h.gate, ("WARNING", "HIGH"))
 
        # ── RECALL notification ───────────────────────────────────────────────
        if h.gate == "RECALL":
            title = (
                recall_summary.get("headline") or "Active Recall"
                if recall_summary else "Active Recall"
            )
            summary = f"Active FDA recall — {title.lower()}."
 
            # WHAT TO DO: LLM action field → legacy what_to_do → deterministic fallback
            action_text = ""
            if recall_summary:
                action_text = (
                    recall_summary.get("action")
                    or recall_summary.get("what_to_do")
                    or ""
                ).strip()
            if not action_text:
                action_text = _fallback_action(recall_severity)
 
            # Build cards — always show at least WHAT HAPPENED + WHAT TO DO.
            # Full fallback chain for every card:
            #   LLM field (recall_summary) → raw FDA text → omit card
            cards: list[dict] = []
 
            if recall_summary:
                what_happened  = recall_summary.get("what_happened", "").strip()
                who_at_risk    = recall_summary.get("who_is_at_risk", "").strip()
                severity_plain = recall_summary.get("severity_plain", "").strip()
                locations      = recall_summary.get("locations", "").strip()
 
                if what_happened:
                    cards.append({"label": "WHAT HAPPENED", "body": what_happened})
                if who_at_risk:
                    cards.append({"label": "WHO IS AT RISK", "body": who_at_risk})
            else:
                # LLM summary not yet available — show raw FDA reason_for_recall
                fda_text = recall_reason.strip()
                if fda_text:
                    cards.append({"label": "WHAT HAPPENED", "body": fda_text})
 
            cards.append({"label": "WHAT TO DO", "body": action_text})
 
            if recall_summary and recall_summary.get("severity_plain"):
                cards.append({
                    "label": "RECALL CLASS",
                    "body":  recall_summary["severity_plain"],
                })
            elif recall_severity:
                cards.append({"label": "RECALL CLASS", "body": recall_severity})
 
            # WHERE RECALLED: LLM-formatted plain English preferred.
            # Fallback to raw distribution_pattern for older DB records
            # stored before the 'locations' field was added to the LLM prompt.
            locations_text = (
                recall_summary.get("locations", "").strip() if recall_summary else ""
            )
            if not locations_text and recall_distribution:
                locations_text = recall_distribution
            if locations_text:
                cards.append({"label": "WHERE RECALLED", "body": locations_text})
 
            notifications.append({
                "type":           ntype,
                "severity":       severity,
                "is_safety_risk": True,
                "title":          title,
                "summary":        summary,
                "cards":          cards,
                "message":        " ".join(
                    c["body"] for c in cards if c["body"]
                ).strip() or h.reason,
            })
 
        # ── ALLERGEN notification ─────────────────────────────────────────────
        elif h.gate == "ALLERGEN":
            # Find the AllergenMatch object(s) that triggered this hard stop
            allergen_name   = "allergen"
            matched_tokens: list[str] = []
            is_advisory     = False   # True if triggered by "may contain" language
 
            for m in report.allergen_matches:
                if (
                    m.allergen.lower() in h.reason.lower()
                    or m.matched_token in h.reason
                ):
                    allergen_name = m.allergen
                    matched_tokens.append(m.matched_token)
                    if m.is_advisory:
                        is_advisory = True
 
            token_list = (
                ", ".join(matched_tokens[:3]) if matched_tokens else "see ingredients"
            )
 
            if is_advisory:
                # ── Advisory path: "may contain" label language ───────────────
                # The allergen was detected in a "May Contain" / "Shared Facility"
                # advisory statement, not confirmed in the ingredient list itself.
                # Verdict is still DONT_BUY but wording makes the distinction clear.
                title   = f"May Contain {allergen_name}"
                summary = (
                    f"This product's label warns it may contain "
                    f"{allergen_name.lower()} (your declared allergen). "
                    f"Cross-contamination is possible."
                )
                cards = [
                    {
                        "label": "ADVISORY WARNING",
                        "body": (
                            f"The label states this product may contain "
                            f"{allergen_name} — detected in the advisory or "
                            f"cross-contact statement, not the ingredient list."
                        ),
                    },
                    {
                        "label": "YOUR ALLERGY",
                        "body": (
                            f"You declared a {allergen_name} allergy. "
                            f"Even trace amounts from cross-contamination can "
                            f"trigger a reaction — do not eat this product."
                        ),
                    },
                    {
                        "label": "WHAT TO DO",
                        "body": (
                            "Do not eat this product. Return it to the store "
                            "for a refund or choose a product with no advisory "
                            f"language for {allergen_name.lower()}."
                        ),
                    },
                ]
            else:
                # ── Confirmed path: allergen in ingredient list ────────────────
                title   = f"Contains {allergen_name}"
                summary = (
                    f"This product contains {allergen_name.lower()} "
                    f"(your declared allergen). "
                    + (
                        "It is also part of an active FDA recall."
                        if report.is_recalled
                        else "It is not part of any active recall."
                    )
                )
                cards = [
                    {
                        "label": "ALLERGEN FOUND",
                        "body": (
                            f"This product contains {allergen_name} "
                            f"({token_list})."
                        ),
                    },
                    {
                        "label": "YOUR ALLERGY",
                        "body": (
                            f"You declared a {allergen_name} allergy. "
                            f"Do not eat this product."
                        ),
                    },
                    {
                        "label": "WHAT TO DO",
                        "body": (
                            "Do not eat this product. You can return it to "
                            "the store even without a receipt if purchased recently."
                        ),
                    },
                ]
                if not report.is_recalled:
                    cards.append({
                        "label": "RECALL STATUS",
                        "body": (
                            "This product is not part of any active FDA recall. "
                            "The allergen concern is based on the ingredient "
                            "list on the label."
                        ),
                    })
 
            notifications.append({
                "type":           ntype,
                "severity":       severity,
                "is_safety_risk": True,
                "title":          title,
                "summary":        summary,
                "cards":          cards,
                "message":        h.reason,   # legacy
            })
 
        # ── DIET_STRICT notification ──────────────────────────────────────────
        elif h.gate == "DIET_STRICT":
            diet_name     = "your diet"
            flagged_token = ""
            for f in report.diet_flags:
                if f.flagged_token in h.reason:
                    diet_name     = f.diet
                    flagged_token = f.flagged_token
                    break
 
            title   = f"Not {diet_name}"
            summary = (
                f"This product contains '{flagged_token}', which is not "
                f"compatible with {diet_name}. "
                f"This is a diet conflict, not a safety risk."
            )
            cards = [
                {
                    "label": "DIET CONFLICT",
                    "body": (
                        f"Contains '{flagged_token}', which is incompatible "
                        f"with {diet_name}."
                    ),
                },
                {
                    "label": "NOT A SAFETY RISK",
                    "body": (
                        "This is a diet preference conflict, not a food safety "
                        "issue. There is no recall or medical allergen concern "
                        "for this product."
                    ),
                },
                {
                    "label": "YOUR PREFERENCE",
                    "body": f"You follow a {diet_name} diet.",
                },
            ]
 
            notifications.append({
                "type":           ntype,
                "severity":       severity,
                "is_safety_risk": False,   # diet preference, not a medical emergency
                "title":          title,
                "summary":        summary,
                "cards":          cards,
                "message":        h.reason,   # legacy
            })
 
        else:
            # Catch-all for any future gate types added to the engine
            notifications.append({
                "type":           ntype,
                "severity":       severity,
                "is_safety_risk": True,
                "title":          "Warning",
                "summary":        h.reason,
                "cards":          [{"label": "DETAIL", "body": h.reason}],
                "message":        h.reason,
            })
 
    # ─────────────────────────────────────────────────────────────────────────
    # LAYER 2: Caution signals → notifications
    # Only reached when no hard stop fired.
    # ─────────────────────────────────────────────────────────────────────────
    for s in report.caution_signals:
        ntype, severity = _CATEGORY_TO_NOTIFICATION.get(
            s.category, ("WARNING", "LOW")
        )
 
        if s.category == "CROSS_CONTACT":
            # POSSIBLE-confidence advisory (reserved — currently not assigned
            # by the engine; "may contain" matches are now PROBABLE → hard stop).
            # Kept here for safety in case a future code path adds POSSIBLE matches.
            title     = "Cross-Contamination Advisory"
            summary   = s.detail
            is_safety = True
            cards     = [
                {
                    "label": "ADVISORY",
                    "body":  s.detail,
                },
                {
                    "label": "WHAT THIS MEANS",
                    "body": (
                        "This allergen was not found in the ingredient list "
                        "itself but appears in a 'may contain' or shared-facility "
                        "warning. Cross-contamination is possible but not confirmed."
                    ),
                },
            ]
 
        elif s.category == "DIET_SOFT":
            # PROBABLE diet flag, or DEFINITE on a non-strict diet (Keto/Paleo)
            title     = "Diet Preference Note"
            summary   = s.detail
            is_safety = False
            cards     = [
                {
                    "label": "DIET CONFLICT",
                    "body":  s.detail,
                },
                {
                    "label": "NOT A SAFETY RISK",
                    "body": (
                        "This is a diet preference mismatch, not a food safety "
                        "issue. There are no allergens or active recalls "
                        "associated with this concern."
                    ),
                },
            ]
 
        elif s.category == "ADDITIVE":
            title     = "Additive Flag"
            summary   = s.detail
            is_safety = False
            cards     = [
                {"label": "ADDITIVE FLAG", "body": s.detail},
            ]
 
        elif s.category == "LOW_CONFIDENCE":
            # Missing or very short ingredient list — conservative unknown
            title     = "Incomplete Data"
            summary   = s.detail
            is_safety = True   # unknown → conservative
            cards     = [
                {
                    "label": "DATA GAP",
                    "body":  s.detail,
                },
            ]
 
        else:
            title     = "Note"
            summary   = s.detail
            is_safety = False
            cards     = [{"label": "DETAIL", "body": s.detail}]
 
        notifications.append({
            "type":           ntype,
            "severity":       severity,
            "is_safety_risk": is_safety,
            "title":          title,
            "summary":        summary,
            "cards":          cards,
            "message":        s.detail,   # legacy flat text
        })
 
    return notifications
 
 
# def _build_notifications(report, recall_summary: Optional[dict] = None,recall_severity: str = "",
#     recall_distribution: str = "",) -> list[dict]:
#     """
#     Convert hard stops and caution signals into a flat, typed notification
#     array the frontend can render directly as colored cards or banners.
 
#     Each notification:
#       {
#         "type":     "RECALL" | "ALLERGEN" | "DIET" | "ADDITIVE" | "WARNING",
#         "severity": "HIGH" | "MEDIUM" | "LOW",
#         "title":    short headline for the card,
#         "message":  full explanation text,
#         "detail":   (recall only) LLM plain-language breakdown if available
#       }
 
#     Recall notifications include both the deterministic alert AND the
#     LLM-generated plain-language summary (headline, what_happened,
#     what_to_do, who_is_at_risk) when available.
 
#     Allergen and diet notifications are always deterministic templates.
#     """
#     notifications: list[dict] = []
 
#     # Hard stops → HIGH severity notifications
#     for h in report.hard_stops:
#         ntype, severity = _GATE_TO_NOTIFICATION.get(h.gate, ("WARNING", "HIGH"))
 
#         if h.gate == "RECALL":
#             # Use LLM headline if available, otherwise generic title
#             title = recall_summary.get("headline", "Active Recall") if recall_summary else "Active Recall"
 
#             # Build enriched message: LLM explanation + deterministic fallback
#             if recall_summary:
#                 message = (
#                     f"{recall_summary.get('what_happened', '')} "
#                     f"{recall_summary.get('what_to_do', '')} "
#                     f"{recall_summary.get('who_is_at_risk', '')} "
#                     f"{recall_summary.get('severity_plain', '')}"
#                 ).strip()
#             else:
#                 message = h.reason
 
#             notification = {
#                 "type":     ntype,
#                 "severity": severity,
#                 "title":    title,
#                 "message":  message,
#             }
 
#             # Include the full LLM breakdown as a separate field
#             # so the frontend can render it as expandable detail
#             if recall_summary:
#                 notification["detail"] = {
#                     "headline":       recall_summary.get("headline", ""),
#                     "what_happened":  recall_summary.get("what_happened", ""),
#                     "what_to_do":     recall_summary.get("what_to_do", ""),
#                     "who_is_at_risk": recall_summary.get("who_is_at_risk", ""),
#                     "severity_plain": recall_summary.get("severity_plain", ""),
#                     locations      = recall_summary.get("locations", "").strip()
#                 }
 
#             notifications.append(notification)
 
#         elif h.gate == "ALLERGEN":
#             title = "Food Sensitivity Detected"
#             for m in report.allergen_matches:
#                 if m.matched_token in h.reason or m.allergen.lower() in h.reason.lower():
#                     title = f"Food Sensitivity: {m.allergen}"
#                     break
#             notifications.append({
#                 "type":     ntype,
#                 "severity": severity,
#                 "title":    title,
#                 "message":  h.reason,
#             })
 
#         elif h.gate == "DIET_STRICT":
#             title = "Diet Violation"
#             for f in report.diet_flags:
#                 if f.flagged_token in h.reason:
#                     title = f"Not {f.diet}"
#                     break
#             notifications.append({
#                 "type":     ntype,
#                 "severity": severity,
#                 "title":    title,
#                 "message":  h.reason,
#             })
 
#         else:
#             notifications.append({
#                 "type":     ntype,
#                 "severity": severity,
#                 "title":    "Warning",
#                 "message":  h.reason,
#             })
 
#     # Caution signals → MEDIUM/LOW severity notifications
#     for s in report.caution_signals:
#         ntype, severity = _CATEGORY_TO_NOTIFICATION.get(s.category, ("WARNING", "LOW"))
 
#         if s.category == "CROSS_CONTACT":
#             title = "Cross-Contact Advisory"
#         elif s.category == "ADDITIVE":
#             title = "Additive Flag"
#         elif s.category == "DIET_SOFT":
#             title = "Diet Preference"
#         elif s.category == "LOW_CONFIDENCE":
#             title = "Low Confidence"
#         else:
#             title = "Note"
 
#         notifications.append({
#             "type":     ntype,
#             "severity": severity,
#             "title":    title,
#             "message":  s.detail,
#         })
 
#     return notifications