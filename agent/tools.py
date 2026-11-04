from mock_data import PRODUCT_CATALOG,RESALE_VALUES,REFURB_COSTS,INVENTORY_DEMAND,DONATION_PARTNERS,RECYCLING_RULES,CARBON_ESTIMATES

def _require(m,k,label):
    if k not in m: raise ValueError(f'Unknown {label}: {k}')
    return m[k]
def get_product_info(sku): return {'sku':sku,**_require(PRODUCT_CATALOG,sku,'SKU')}
def get_resale_value(sku,condition_grade): return {'sku':sku,'condition_grade':condition_grade,'estimated_resale_usd':_require(_require(RESALE_VALUES,sku,'SKU'),condition_grade,'condition grade')}
def get_refurb_cost(sku,condition_grade): return {'sku':sku,'condition_grade':condition_grade,'estimated_refurb_cost_usd':_require(_require(REFURB_COSTS,sku,'SKU'),condition_grade,'condition grade')}
def get_inventory_demand(sku): return {'sku':sku,**_require(INVENTORY_DEMAND,sku,'SKU')}
def get_donation_partners(category,condition_grade): return [] if condition_grade=='D' else [p for p in DONATION_PARTNERS if category in p['accepts']]
def get_recycling_rules(category): return {'category':category,**_require(RECYCLING_RULES,category,'category')}
def get_carbon_estimate(destination,category): return {'destination':destination,'category':category,'carbon_avoided_kg':_require(_require(CARBON_ESTIMATES,destination,'destination'),category,'category')}
