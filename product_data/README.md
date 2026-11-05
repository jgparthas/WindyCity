# Cosmic Mart Returns - Synthetic Data (Data Lead)

SYNTHETIC DATA - PROTOTYPE ONLY

Products, prices, repair costs, demand, recall information, donation/recycling rules, and carbon factors are synthetic assumptions created for prototype testing. All monetary amounts are in USD.

## Files

### returns.json
64 synthetic return records used by the Rule Gate and agent through get_return_record.

### product_catalog.csv
Product reference data used by the Rule Gate (R02, R04, R06) and get_product_info: category, price, warranty, has_battery, has_data_storage, weight_kg, donation eligibility, recyclability, and placeholder carbon factors.

### recalled_skus.csv
Synthetic recalled SKU reference data used by the Rule Gate.

### unit_economics.csv
Per-return resale value as-is, refurbishment cost, post-refurbishment value, and inventory demand. Read by get_resale_value, get_refurb_cost, and get_inventory_demand.

### donation_partners.csv
Mock Cosmic Nexus donation partners, accepted categories, minimum condition requirements, and data-device policies. Read by get_donation_partners.

### recycling_rules.csv
Mock recycling pathways by category, including battery handling and data-destruction policies. Read by get_recycling_rules.

### eval_labels.csv
TESTING ONLY - NEVER GIVE THIS FILE TO THE AGENT.

Contains the expected gate status, gate reasons, restrictions, destination, recovery value, carbon estimate, human-review requirement, prototype baseline decision, case type, and rationale.

## Dataset Conventions

- 64 total return records (TC-01 through TC-32 are the original set; TC-33 through TC-64 were added to balance the outcomes, with extra Waste cases).
- Catalog-corrected mix: 36 gadgets, 12 fashion, and 15 home_lifestyle (plus TC-22, whose SKU is deliberately not in the catalog).
- Raw intake contains 36 gadgets, 12 fashion, and 16 home_lifestyle because TC-13 intentionally contains an incorrect category to test catalog override behavior.
- 7 of 64 returns are intentionally ungraded so the agent must interpret the notes.
- received_at uses local receiving-site time with no timezone suffix.
- customer_notes uses null when no notes are available.
- SKU format is GAD-####, FSH-####, or HOM-####.
- Economics and demand are assigned per returned unit, not per SKU.
- Two returns of the same SKU may therefore have different resale and refurbishment values.
- Carbon values are placeholder prototype factors until the team agrees on a source or methodology. weight_kg is included so the team can calculate carbon from weight instead; both can coexist until the method is chosen.
- test_case_id (TC-01 through TC-64) links returns.json, unit_economics.csv, and eval_labels.csv.
- Use test_case_id rather than return_id when joining test data because RET-2001 intentionally appears twice to test duplicate detection.
- TC-22 through TC-24 have no unit-economics rows because those records are expected to stop at the Rule Gate.
- Boolean fields use true / false.
- An empty CSV cell represents null or unknown.
- Policy fields such as data_device_policy, data_destruction_policy, and inventory_demand are text values.
- Money fields ending in _usd use two decimal places.
- donation_eligible accepts true, false, or null. Unknown eligibility must not be treated as false. If donation is otherwise the recommended route, unknown eligibility requires human review.

## Data-Wipe Restriction

DATA_WIPE_REQUIRED_BEFORE_RELEASE

A product with has_data_storage = true must complete data wiping before it can be:

- Restocked (back to stock, whether as new or open-box)
- Donated
- Released after refurbishment

Refurbishment itself may occur before the wipe.

## Condition Grades

- A = Like new, no visible wear
- B = Minor cosmetic wear, fully functional
- C = Visible wear or intermittent functionality issues
- D = Heavily damaged or non-functional
- null = Not graded

## Hazard Flag Mapping

PROPOSED - TEAM TO CONFIRM

Blocking hazards result in HAZARD and do not continue to the agent:

- swollen_battery
- overheating_or_burn_marks
- leaking_fluid
- mold_or_odor
- other_hazard

Non-blocking hazards:

- liquid_damage
- cracked_glass_or_casing

A non-blocking hazard results in PASS with a WARN reason and continues to the agent.

## Gate Rules Used for the Answer Key

- R02: SKU not found in product catalog -> INCOMPLETE
- R03: SKU appears on recall list -> HAZARD
- R04: Blocking structured hazard flag -> HAZARD
- R05: Hazard keyword detected in customer notes -> HAZARD
- R06: has_data_storage is true and data_wipe_confirmed is not true -> PASS with CONSTRAIN reason and DATA_WIPE_REQUIRED_BEFORE_RELEASE
- R07: Missing condition grade -> PASS with WARN reason
- R08: Duplicate return_id -> INCOMPLETE
- R09: purchase_date occurs after received_at -> INCOMPLETE
- R10: Return category disagrees with product catalog -> PASS with WARN reason; catalog value wins
- R11: Non-blocking hazard flag (liquid_damage, cracked_glass_or_casing) -> PASS with WARN reason

Rule IDs match the Rule Gate owner's v1 rule reference. R01 (required field missing) is not separately labeled in this set; the Gate owner can test it directly.

Valid Gate statuses are only:

- PASS
- HAZARD
- INCOMPLETE

WARN and CONSTRAIN are reasons attached to PASS records, not separate Gate statuses.

## Agent Decision Rules Used for the Answer Key

These rules are used to create the expected outcomes in the synthetic evaluation dataset.

1. If condition cannot reasonably be determined from the grade or notes -> HUMAN_REVIEW

2. If the item works (or is unused or like new), requires no repair, and its as-is resale value is at least $50 -> RESTOCK. Restock and resell are one outcome; there is no separate RESELL destination.

3. If refurbishment cost is no more than 50% of post-refurbishment value, net recovery is at least $75, and demand is not low -> REFURBISH

4. If refurbishment cost is greater than 50% and no more than 100% of post-refurbishment value -> HUMAN_REVIEW

5. If refurbishment otherwise qualifies but inventory demand is low -> HUMAN_REVIEW

6. If the item works, its as-is value is under $50, and it is donation eligible -> DONATE

7. If donation eligibility is unknown when donation would otherwise be recommended -> HUMAN_REVIEW

8. Otherwise, including uneconomic repairs or non-functional products without a better recovery path -> RECYCLE, or WASTE when the catalog says the product is not recyclable

These are prototype labeling rules used to create an explainable evaluation set. They are not presented as confirmed Cosmic Mart business policies.

## Prototype Baseline Assumption

For prototype comparison purposes:

Grade A -> RESTOCK

All other grades -> LIQUIDATE

This simplified baseline is used only to compare prototype outcomes. It is not presented as Cosmic Mart's confirmed current-state returns process.

## Coverage

Expected destination coverage:

- RESTOCK: 11
- REFURBISH: 10
- DONATE: 7
- RECYCLE: 9
- WASTE: 13
- HAZARD_REVIEW: 5
- HUMAN_REVIEW: 9

Gate status coverage:

- PASS: 55
- HAZARD: 5
- INCOMPLETE: 4

Nine PASS cases also contain WARN reasons.

## Edge Cases Included

The synthetic evaluation set includes:

- Swollen battery hazard
- Burn-mark / overheating hazard
- Recalled SKU
- Hazard detected only in customer notes
- Unknown SKU
- Duplicate Return ID
- Purchase date after received date
- Missing condition grade with clear notes
- Missing condition grade with vague notes
- Condition grade conflicting with customer notes
- Return reason conflicting with customer notes
- Borderline refurbishment economics
- Repairable product with low demand
- Unknown donation eligibility
- Data wipe not confirmed
- Incorrect intake category
- Misspelled/messy customer notes
- One adversarial/untrusted free-text test case

## Recommended Demo Cases

TC-02 / RET-2002
RESTOCK - sealed product returned to inventory.

TC-05 / RET-2005
REFURBISH - $80 refurbishment cost supports $350 post-refurbishment value, with a data-wipe restriction.

TC-09 / RET-2009
DONATE - functional item with low resale value.

TC-12 / RET-2012
RECYCLE - refurbishment costs more than the product's post-refurbishment value.

TC-19 / RET-2019
HAZARD_REVIEW - swollen battery is stopped by the Rule Gate.

TC-32 / RET-2030
Adversarial free-text test - untrusted customer notes must not override structured condition and policy data.

## Bonus Demo Cases

TC-26
Grade A and changed_mind suggest a simple return, but the free-text notes reveal a product fault. Expected outcome: REFURBISH.

TC-21
The associate did not enter a structured hazard flag, but the customer notes contain hazard information that should be caught before reaching normal agent reasoning.

TC-31
Refurbishment economics appear favorable, but inventory demand is low. Expected outcome: HUMAN_REVIEW.

## Value Summary - Synthetic Prototype Results

- 28 of 64 returns receive a second life through Restock, Refurbish, or Donate.
- 9 additional returns are routed to Recycle, and 13 go to Waste because the item cannot be recycled.
- Under the prototype definition, 37 of 64 returns are kept out of landfill.
- 14 of 64 returns are routed to a human: 5 Hazard Review cases and 9 Human Review cases.
- Approximately $4,740 of synthetic value is recovered.
- Approximately 805 kg CO2e is avoided using placeholder carbon factors.
- Under the simplified prototype baseline, two hazardous items and one faulty Grade-A product would have been labeled for restock.

Value-slide wording:

"Prototype estimate based on synthetic returns and placeholder CO2e factors."

## Assumptions and Limitations

- All return records are synthetic.
- No real customer information is included.
- Product prices, resale values, refurbishment costs, demand, recalls, donation rules, recycling rules, and carbon factors are prototype assumptions.
- All monetary values are in USD.
- Customer notes are English text only.
- Photos are outside the current prototype scope.
- Carbon calculations are illustrative until the team agrees on a factor source or methodology.
- Shipping distance is simplified or outside the current prototype scope.
- Donation and refurbishment capacity are simplified.
- Real-world data-wipe verification is outside the current prototype scope.