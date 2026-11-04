"""MCP wrappers that expose tools.py to the Claude agent."""
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
    return {"content": [{"type": "text", "text": json.dumps(data)}]}


def _error(message: str) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": message}], "isError": True}


def _call(fn, *args):
    try:
        return _result(fn(*args))
    except ValueError as error:  # includes data_loader.MissingDataError
        return _error(str(error))


@tool(
    "get_product_info",
    "Get trusted catalog facts for a SKU: category, price, warranty, "
    "has_battery, has_data_storage, weight_kg, donation_eligible "
    "(null = unknown, not false), recyclable.",
    {"sku": str},
)
async def product_info(args: dict[str, Any]) -> dict[str, Any]:
    return _call(get_product_info, args["sku"])


@tool(
    "get_resale_value",
    "Get the as-is resale value of this returned unit, by return_id.",
    {"return_id": str},
)
async def resale_value(args: dict[str, Any]) -> dict[str, Any]:
    return _call(get_resale_value, args["return_id"])


@tool(
    "get_refurb_cost",
    "Get the refurbishment cost and post-refurbishment value of this "
    "returned unit, by return_id.",
    {"return_id": str},
)
async def refurb_cost(args: dict[str, Any]) -> dict[str, Any]:
    return _call(get_refurb_cost, args["return_id"])


@tool(
    "get_inventory_demand",
    "Get inventory demand (HIGH, MEDIUM, LOW) for this returned unit, "
    "by return_id.",
    {"return_id": str},
)
async def inventory_demand(args: dict[str, Any]) -> dict[str, Any]:
    return _call(get_inventory_demand, args["return_id"])


@tool(
    "get_donation_partners",
    "Find Cosmic Nexus donation partners whose category and minimum "
    "condition rules the item meets. Includes each partner's "
    "data_device_policy.",
    {"category": str, "condition_grade": str},
)
async def donation_partners(args: dict[str, Any]) -> dict[str, Any]:
    return _call(
        get_donation_partners, args["category"], args["condition_grade"]
    )


@tool(
    "get_recycling_rules",
    "Get recycling requirements for a category (gadgets, fashion, "
    "home_lifestyle, or hazard).",
    {"category": str},
)
async def recycling_rules(args: dict[str, Any]) -> dict[str, Any]:
    return _call(get_recycling_rules, args["category"])


@tool(
    "get_carbon_estimate",
    "Get placeholder carbon avoided (kg CO2e) for a SKU and destination "
    "(restock, refurbish, donate, recycle).",
    {"sku": str, "destination": str},
)
async def carbon_estimate(args: dict[str, Any]) -> dict[str, Any]:
    return _call(get_carbon_estimate, args["sku"], args["destination"])
