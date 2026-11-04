import json
from typing import Any

from claude_agent_sdk import tool

from tools import (
    get_carbon_estimate,
    get_donation_partners,
    get_inventory_demand,
    get_product_info,
    get_recycling_rules,
    get_refurb_cost,
    get_resale_value,
)


def _result(data: Any) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(data),
            }
        ]
    }


def _error(message: str) -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "text",
                "text": message,
            }
        ],
        "isError": True,
    }


@tool(
    "get_product_info",
    "Get trusted catalog information for a product SKU.",
    {"sku": str},
)
async def product_info(
    args: dict[str, Any],
) -> dict[str, Any]:
    try:
        return _result(get_product_info(args["sku"]))
    except ValueError as error:
        return _error(str(error))


@tool(
    "get_resale_value",
    "Get the estimated resale value for a SKU and condition grade.",
    {
        "sku": str,
        "condition_grade": str,
    },
)
async def resale_value(
    args: dict[str, Any],
) -> dict[str, Any]:
    try:
        return _result(
            get_resale_value(
                args["sku"],
                args["condition_grade"],
            )
        )
    except ValueError as error:
        return _error(str(error))


@tool(
    "get_refurb_cost",
    "Get the estimated refurbishment cost for a product.",
    {
        "sku": str,
        "condition_grade": str,
    },
)
async def refurb_cost(
    args: dict[str, Any],
) -> dict[str, Any]:
    try:
        return _result(
            get_refurb_cost(
                args["sku"],
                args["condition_grade"],
            )
        )
    except ValueError as error:
        return _error(str(error))


@tool(
    "get_inventory_demand",
    "Get current demand and inventory information for a SKU.",
    {"sku": str},
)
async def inventory_demand(
    args: dict[str, Any],
) -> dict[str, Any]:
    try:
        return _result(
            get_inventory_demand(args["sku"])
        )
    except ValueError as error:
        return _error(str(error))


@tool(
    "get_donation_partners",
    "Find Cosmic Nexus partners that accept an item.",
    {
        "category": str,
        "condition_grade": str,
    },
)
async def donation_partners(
    args: dict[str, Any],
) -> dict[str, Any]:
    try:
        return _result(
            get_donation_partners(
                args["category"],
                args["condition_grade"],
            )
        )
    except ValueError as error:
        return _error(str(error))


@tool(
    "get_recycling_rules",
    "Get recycling requirements for a product category.",
    {"category": str},
)
async def recycling_rules(
    args: dict[str, Any],
) -> dict[str, Any]:
    try:
        return _result(
            get_recycling_rules(args["category"])
        )
    except ValueError as error:
        return _error(str(error))


@tool(
    "get_carbon_estimate",
    "Get estimated carbon avoided for a destination and category.",
    {
        "destination": str,
        "category": str,
    },
)
async def carbon_estimate(
    args: dict[str, Any],
) -> dict[str, Any]:
    try:
        return _result(
            get_carbon_estimate(
                args["destination"],
                args["category"],
            )
        )
    except ValueError as error:
        return _error(str(error))