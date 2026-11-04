"""Rule Gate v1 - deterministic pre-filter that runs before the agent.

evaluate(record, catalog, recalled, seen_ids) -> gate result dict.
evaluate_batch(records, catalog, recalled)    -> list of results, file order.

Conventions (see rules_v1.md):
- Timestamps are local receiving-site time, ISO 8601, NO timezone suffix
  (matches product_data). evaluated_at uses the same convention.
- Enums in the output are lowercase.
- Duplicate return_id: first occurrence in file order passes through the other
  rules; later copies get R08.
"""
import copy
import csv
import json
import re
from datetime import datetime
from pathlib import Path

RULE_VERSION = "v1"

# "resell" was merged into "restock": a sellable working item goes back to stock.
ALL_DESTINATIONS = ["restock", "refurbish", "donate", "recycle"]
CATEGORIES = {"gadgets", "fashion", "home_lifestyle"}
CHANNELS = {"warehouse", "store"}
REASON_CODES = {"defective", "damaged_in_transit", "not_as_described",
                "wrong_item_received", "changed_mind", "size_or_fit", "other"}
GRADES = {"A", "B", "C", "D"}

# R01: these must be present (non-null, non-empty). customer_notes,
# condition_grade, hazard_flags and data_wipe_confirmed may be null.
REQUIRED_FIELDS = ["return_id", "sku", "category", "original_price",
                   "purchase_date", "received_at", "received_channel",
                   "return_reason_code"]

BLOCKING_FLAGS = ["swollen_battery", "overheating_or_burn_marks",
                  "leaking_fluid", "mold_or_odor", "other_hazard"]
NON_BLOCKING_FLAGS = ["liquid_damage", "cracked_glass_or_casing"]

# R05 keyword list (v1). Whole-word / phrase match, case-insensitive.
# Deliberately excludes "bulging" and "scorch" so flagged records (TC-19, TC-30)
# produce R04 only, as in the answer key.
HAZARD_KEYWORDS = ["burning", "burnt", "smoke", "smoking", "on fire",
                   "caught fire", "flames", "sparks", "sparking", "melted",
                   "melting", "exploded", "explosion", "leaking", "leaked",
                   "swollen", "mold", "mould", "moldy", "mouldy"]
_KEYWORD_RE = re.compile(
    r"\b(" + "|".join(re.escape(k) for k in HAZARD_KEYWORDS) + r")\b", re.I)


# ---------------------------------------------------------------- loaders
def _bool(v):
    v = (v or "").strip().lower()
    return True if v == "true" else False if v == "false" else None


def load_catalog(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for c in ("has_battery", "has_data_storage", "donation_eligible",
                  "recyclable"):
            if c in r:
                r[c] = _bool(r[c])
    return {r["sku"]: r for r in rows}


def load_recalled(path):
    with open(path, newline="", encoding="utf-8") as f:
        return {r["sku"]: r for r in csv.DictReader(f)}


def load_returns(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------- helpers
def _reason(rule_id, severity, message):
    return {"rule_id": rule_id, "severity": severity, "message": message}


def _blank(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _parse_date(s):
    return datetime.strptime(s[:10], "%Y-%m-%d").date()


def _now():
    return datetime.now().replace(microsecond=0).isoformat()


# ------------------------------------------------------------------ gate
def evaluate(record, catalog, recalled, seen_ids=None, evaluated_at=None):
    """Evaluate one return record. seen_ids is a set of already-seen
    return_ids (mutated); pass the same set across a batch for R08."""
    seen_ids = seen_ids if seen_ids is not None else set()
    block = []      # hazard BLOCK reasons
    incomplete = []  # incomplete BLOCK reasons
    soft = []       # WARN / CONSTRAIN, kept only for PASS

    # R01 required fields
    missing = [f for f in REQUIRED_FIELDS if _blank(record.get(f))]
    if missing:
        incomplete.append(_reason(
            "R01", "BLOCK", "Required field missing: " + ", ".join(missing)))

    # R08 duplicate return_id
    rid = record.get("return_id")
    if not _blank(rid):
        if rid in seen_ids:
            incomplete.append(_reason(
                "R08", "BLOCK", f"Duplicate return_id {rid}"))
        seen_ids.add(rid)

    # R02 SKU in catalog
    sku = record.get("sku")
    product = catalog.get(sku) if not _blank(sku) else None
    if not _blank(sku) and product is None:
        incomplete.append(_reason(
            "R02", "BLOCK", f"SKU {sku} not found in product_catalog"))

    # R09 purchase after receipt (date part only; same day is fine)
    try:
        if not _blank(record.get("purchase_date")) and \
                not _blank(record.get("received_at")):
            if _parse_date(record["purchase_date"]) > \
                    _parse_date(record["received_at"]):
                incomplete.append(_reason(
                    "R09", "BLOCK", "purchase_date is after received_at"))
    except ValueError:
        incomplete.append(_reason(
            "R01", "BLOCK", "purchase_date or received_at is not a valid date"))

    # R03 recalled SKU
    if not _blank(sku) and sku in recalled:
        why = recalled[sku].get("recall_reason", "")
        block.append(_reason("R03", "BLOCK", f"SKU is recalled: {why}"))

    # R04 blocking hazard flags
    flags = record.get("hazard_flags") or []
    hit = [f for f in flags if f in BLOCKING_FLAGS]
    if hit:
        block.append(_reason(
            "R04", "BLOCK", "Blocking hazard flag set: " + ", ".join(hit)))

    # R05 hazard keywords in notes (notes are untrusted data, never executed)
    notes = record.get("customer_notes")
    if isinstance(notes, str):
        kw = sorted({m.lower() for m in _KEYWORD_RE.findall(notes)})
        if kw:
            block.append(_reason(
                "R05", "BLOCK",
                "Hazard keyword in customer_notes: " + ", ".join(kw)))

    # PASS-only reasons
    if product is not None:
        if product.get("has_data_storage") and \
                record.get("data_wipe_confirmed") is not True:
            soft.append(_reason(
                "R06", "CONSTRAIN",
                "Product has data storage and wipe is not confirmed; wipe "
                "required before any resale or donation"))
        rec_cat = record.get("category")
        if rec_cat != product["category"]:
            soft.append(_reason(
                "R10", "WARN",
                f"Record category '{rec_cat}' disagrees with catalog "
                f"'{product['category']}'; catalog value used"))
    if _blank(record.get("condition_grade")):
        soft.append(_reason(
            "R07", "WARN", "Condition grade missing; infer from notes"))
    nb = [f for f in flags if f in NON_BLOCKING_FLAGS]
    if nb:
        soft.append(_reason(
            "R11", "WARN", "Non-blocking hazard flag present: " + ", ".join(nb)))

    # Precedence: HAZARD > INCOMPLETE > PASS
    if block:
        status, route, dest = "HAZARD", "review_queue", "human_review"
        reasons = block + incomplete
        allowed, wipe = [], False
    elif incomplete:
        status, route, dest = "INCOMPLETE", "review_queue", "human_review"
        reasons = incomplete
        allowed, wipe = [], False
    else:
        status, route, dest = "PASS", "agent", None
        reasons = soft
        allowed = list(ALL_DESTINATIONS)
        # Catalog-driven narrowing. Unknown (None) eligibility is NOT false.
        if product.get("donation_eligible") is False:
            allowed.remove("donate")
        if product.get("recyclable") is False:
            allowed.remove("recycle")
        wipe = any(r["rule_id"] == "R06" for r in reasons)

    return {
        "return_id": rid,
        "gate_status": status,
        "route": route,
        "proposed_destination": dest,
        "reasons": reasons,
        "constraints": {"allowed_destinations": allowed,
                        "data_wipe_required": wipe},
        "record": copy.deepcopy(record),
        "rule_version": RULE_VERSION,
        "evaluated_at": evaluated_at or _now(),
    }


def evaluate_batch(records, catalog, recalled, evaluated_at=None):
    seen = set()
    return [evaluate(r, catalog, recalled, seen, evaluated_at)
            for r in records]


if __name__ == "__main__":
    import sys
    base = Path(sys.argv[1] if len(sys.argv) > 1 else
                Path(__file__).parent.parent / "product_data")
    cat = load_catalog(base / "product_catalog.csv")
    rec = load_recalled(base / "recalled_skus.csv")
    out = evaluate_batch(load_returns(base / "returns.json"), cat, rec)
    print(json.dumps(out, indent=2))
