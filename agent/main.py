import asyncio
import json
from collections import Counter

from agent import recommend
from models import GateResult, ReturnRecord


def cases():
    all_routes = [
        "restock",
        "refurbish",
        "resell",
        "donate",
        "recycle",
    ]

    return [
        GateResult(
            status="PASS",
            allowed_destinations=all_routes,
            constraints=["data_wipe_required"],
            record=ReturnRecord(
                return_id="RET-001",
                sku="GAD-1001",
                category="gadgets",
                product_name="Tablet",
                original_price_usd=499,
                customer_notes="Works well. Open box.",
                condition_grade="A",
            ),
        ),
        GateResult(
            status="PASS",
            allowed_destinations=all_routes,
            constraints=["data_wipe_required"],
            record=ReturnRecord(
                return_id="RET-002",
                sku="GAD-1002",
                category="gadgets",
                product_name="Smartwatch",
                original_price_usd=129,
                customer_notes=(
                    "Screen flickers sometimes and box is gone."
                ),
                condition_grade="C",
            ),
        ),
        GateResult(
            status="PASS",
            allowed_destinations=all_routes,
            constraints=[],
            record=ReturnRecord(
                return_id="RET-003",
                sku="APP-2001",
                category="apparel",
                product_name="Winter jacket",
                original_price_usd=65,
                customer_notes=(
                    "Wrong size. Tags removed but clean."
                ),
                condition_grade="B",
            ),
        ),
        GateResult(
            status="PASS",
            allowed_destinations=[
                "donate",
                "recycle",
            ],
            constraints=["secondary_sale_not_allowed"],
            record=ReturnRecord(
                return_id="RET-004",
                sku="HOM-3001",
                category="home",
                product_name="Countertop appliance",
                original_price_usd=110,
                customer_notes=(
                    "Works, but the discontinued cosmetic "
                    "finish cannot be resold."
                ),
                condition_grade="C",
            ),
        ),
        GateResult(
            status="PASS",
            allowed_destinations=["recycle"],
            constraints=["reuse_quality_threshold_failed"],
            record=ReturnRecord(
                return_id="RET-005",
                sku="HOM-3002",
                category="home",
                product_name="Damaged table lamp",
                original_price_usd=45,
                customer_notes=(
                    "Cracked housing and exposed internal "
                    "bracket; electrical components removed."
                ),
                condition_grade="D",
            ),
        ),
    ]


async def main():
    results = []

    for case in cases():
        print(
            f"\n=== {case.record.return_id}: "
            f"{case.record.product_name} ==="
        )

        result = await recommend(case)
        results.append(result)

        print(
            json.dumps(
                result.model_dump(),
                indent=2,
            )
        )

    hazard = GateResult(
        status="HAZARD",
        allowed_destinations=[],
        constraints=["do_not_route_autonomously"],
        reasons=["swollen_battery"],
        record=ReturnRecord(
            return_id="RET-006",
            sku="GAD-1003",
            category="gadgets",
            product_name="Portable speaker",
            original_price_usd=79,
            customer_notes="Battery casing is swollen.",
            condition_grade="D",
        ),
    )

    print(
        "\n=== RET-006: gate-owned escalation ==="
    )
    print(hazard.model_dump_json(indent=2))
    print(
        "Agent intentionally not called because "
        "the Rule Gate returned HAZARD."
    )

    destination_counts = Counter(
        result.recommended_destination
        for result in results
    )

    batch_summary = {
        "returns_recommended": len(results),
        "destinations": dict(destination_counts),
        "total_expected_recovery_usd": round(
            sum(
                result.expected_recovery_usd
                for result in results
            ),
            2,
        ),
        "total_carbon_avoided_kg": round(
            sum(
                result.estimated_carbon_emission_avoided_kg
                for result in results
            ),
            1,
        ),
        "human_review_required": len(results) + 1,
    }

    print("\n=== BATCH SUMMARY ===")
    print(
        json.dumps(
            batch_summary,
            indent=2,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())