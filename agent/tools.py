"""Read-only tool functions. Every value comes from product_data/ through
data_loader; nothing is hard-coded here."""
from __future__ import annotations

import data_loader as dl

REUSE_DESTINATIONS = {'restock', 'refurbish', 'donate'}


def _require(m, k, label):
    if k not in m:
        raise ValueError(f'Unknown {label}: {k}')
    return m[k]


def _econ(return_id):
    return _require(dl.unit_economics(), return_id,
                    'return_id (no unit economics row)')


def get_product_info(sku):
    row = _require(dl.catalog(), sku, 'SKU')
    return {
        'sku': sku,
        'product_name': row['product_name'],
        'category': row['category'],
        'original_price': float(row['original_price']),
        'warranty_months': int(row['warranty_months']),
        'has_battery': row['has_battery'],
        'has_data_storage': row['has_data_storage'],
        'weight_kg': float(row['weight_kg']),
        # null = unknown; unknown must NOT be treated as false.
        'donation_eligible': row['donation_eligible'],
        'recyclable': row['recyclable'],
    }


def get_resale_value(return_id):
    """As-is resale value of this returned unit."""
    return {'return_id': return_id,
            'estimated_resale_usd': _econ(return_id)['resale_as_is_usd']}


def get_refurb_cost(return_id):
    e = _econ(return_id)
    return {'return_id': return_id,
            'estimated_refurb_cost_usd': e['refurb_cost_usd'],
            'post_refurb_value_usd': e['post_refurb_value_usd']}


def get_inventory_demand(return_id):
    return {'return_id': return_id,
            'demand_level': _econ(return_id)['inventory_demand']}


def get_donation_partners(category, condition_grade):
    """Partners whose category and minimum-condition rules the item meets.
    Items graded D, or with no grade, match no partner."""
    if condition_grade not in dl.GRADE_ORDER:
        return []
    rank = dl.GRADE_ORDER.index(condition_grade)
    return [p for p in dl.donation_partners()
            if category in p['accepts_categories']
            and rank <= dl.GRADE_ORDER.index(p['min_condition'])]


def get_recycling_rules(category):
    """category is gadgets | fashion | home_lifestyle | hazard."""
    return dict(_require(dl.recycling_rules(), category, 'category'))


def get_carbon_estimate(sku, destination):
    """Placeholder carbon factors from the catalog (kg CO2e avoided)."""
    row = _require(dl.catalog(), sku, 'SKU')
    if destination in REUSE_DESTINATIONS:
        col = 'carbon_kg_avoided_if_reused'
    elif destination == 'waste':
        return {'sku': sku, 'destination': destination,
                'carbon_avoided_kg': 0.0}
    elif destination == 'recycle':
        col = 'carbon_kg_avoided_if_recycled'
    else:
        raise ValueError(f'Unknown destination: {destination}')
    return {'sku': sku, 'destination': destination,
            'carbon_avoided_kg': float(row[col])}
