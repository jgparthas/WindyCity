"""Loads the reference data in product_data/ for the agent's tools.

The Rule Gate and the agent read the SAME files (catalog and recalled SKUs
through rule_gate's own loaders), so SKUs, categories and prices cannot drift.
Set COSMIC_DATA_DIR to point at a different data folder.
"""
from __future__ import annotations

import csv
import json
import os
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.environ.get('COSMIC_DATA_DIR', ROOT / 'product_data'))

# One place that makes the rule_gate package importable.
_GATE_DIR = str(ROOT / 'rule_gate')
if _GATE_DIR not in sys.path:
    sys.path.insert(0, _GATE_DIR)

import rule_gate  # noqa: E402

# Condition grades, best to worst.
GRADE_ORDER = ['A', 'B', 'C', 'D']

# Expected columns of unit_economics.csv (per returned unit). ASSUMED from the
# product_data README until the data lead confirms; change names here only.
ECON_KEY = 'return_id'
ECON_COLUMNS = {
    'resale_as_is_usd': 'resale_as_is_usd',
    'refurb_cost_usd': 'refurb_cost_usd',
    'post_refurb_value_usd': 'post_refurb_value_usd',
    'inventory_demand': 'inventory_demand',  # HIGH | MEDIUM | LOW
}


class MissingDataError(ValueError):
    pass


def _csv(name: str) -> list[dict]:
    path = DATA_DIR / name
    if not path.exists():
        raise MissingDataError(f'{path} not found.')
    with open(path, newline='', encoding='utf-8') as f:
        return list(csv.DictReader(f))


def _bool(v):
    v = (v or '').strip().lower()
    return True if v == 'true' else False if v == 'false' else None


def _num(v):
    v = (v or '').strip()
    return float(v) if v else None


@lru_cache
def catalog() -> dict:
    """sku -> catalog row (rule_gate.load_catalog; booleans parsed)."""
    return rule_gate.load_catalog(DATA_DIR / 'product_catalog.csv')


@lru_cache
def recalled() -> dict:
    return rule_gate.load_recalled(DATA_DIR / 'recalled_skus.csv')


@lru_cache
def returns() -> list[dict]:
    return rule_gate.load_returns(DATA_DIR / 'returns.json')


@lru_cache
def recycling_rules() -> dict:
    out = {}
    for r in _csv('recycling_rules.csv'):
        r['handles_batteries'] = _bool(r['handles_batteries'])
        out[r['category']] = r
    return out


@lru_cache
def donation_partners() -> list[dict]:
    out = []
    for r in _csv('donation_partners.csv'):
        r['accepts_categories'] = [
            c for c in r['accepts_categories'].split(';') if c]
        r['must_be_functional'] = _bool(r['must_be_functional'])
        out.append(r)
    return out


@lru_cache
def unit_economics() -> dict:
    """return_id -> economics row. Raises MissingDataError if the data lead's
    unit_economics.csv is not in the data folder."""
    rows = _csv('unit_economics.csv')
    out = {}
    for r in rows:
        key = r[ECON_KEY]
        if key in out:
            raise MissingDataError(
                f'Duplicate {ECON_KEY} {key} in unit_economics.csv; economics '
                'are per returned unit and must be keyed uniquely.')
        out[key] = {
            'resale_as_is_usd': _num(r.get(ECON_COLUMNS['resale_as_is_usd'])),
            'refurb_cost_usd': _num(r.get(ECON_COLUMNS['refurb_cost_usd'])),
            'post_refurb_value_usd':
                _num(r.get(ECON_COLUMNS['post_refurb_value_usd'])),
            'inventory_demand':
                (r.get(ECON_COLUMNS['inventory_demand']) or '').strip().upper()
                or None,
        }
    return out


def economics_available() -> bool:
    return (DATA_DIR / 'unit_economics.csv').exists()


def clear_caches() -> None:
    for fn in (catalog, recalled, returns, recycling_rules,
               donation_partners, unit_economics):
        fn.cache_clear()
