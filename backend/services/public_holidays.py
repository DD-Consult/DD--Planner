"""Public holidays by region (Australia: National / NSW / QLD).

Fetches from the free Nager.Date API (no key) and upserts into holidays_collection
so public holidays behave like company holidays everywhere (capacity, timesheet
auto-fill). Auto-sourced holidays are tagged `source: "auto"` + `region`; manual
entries (source absent/"manual") are never touched by refresh.
"""
import logging
from datetime import datetime, timezone
from typing import Tuple

import httpx

from database import holidays_collection, settings_collection

logger = logging.getLogger(__name__)

NAGER_BASE = "https://date.nager.at/api/v3/PublicHolidays"

# Supported regions. Each AU region = national holidays + that state's holidays.
REGIONS = {
    "AU-NAT": {"country": "AU", "label": "Australia — National", "county": None},
    "AU-NSW": {"country": "AU", "label": "Australia — NSW", "county": "AU-NSW"},
    "AU-QLD": {"country": "AU", "label": "Australia — QLD", "county": "AU-QLD"},
}
DEFAULT_REGION = "AU-NAT"


async def get_region_setting() -> dict:
    """Return {region, label} — the workspace's configured holiday region."""
    doc = await settings_collection.find_one({"type": "holiday_region"})
    region = (doc or {}).get("region") or DEFAULT_REGION
    if region not in REGIONS:
        region = DEFAULT_REGION
    return {"region": region, "label": REGIONS[region]["label"], "available": [
        {"value": k, "label": v["label"]} for k, v in REGIONS.items()
    ]}


async def set_region_setting(region: str) -> dict:
    if region not in REGIONS:
        region = DEFAULT_REGION
    await settings_collection.update_one(
        {"type": "holiday_region"},
        {"$set": {"type": "holiday_region", "region": region}},
        upsert=True,
    )
    return {"region": region, "label": REGIONS[region]["label"]}


def _applies_to_region(holiday: dict, county: str) -> bool:
    """A holiday applies if it's national (global/counties empty) OR its counties
    include the region's state code."""
    counties = holiday.get("counties")
    if not counties:  # national / applies everywhere
        return True
    if county and county in counties:
        return True
    return False


async def fetch_and_store_holidays(year: int, region: str = None) -> Tuple[int, str]:
    """Fetch public holidays for the year+region from Nager.Date and upsert them,
    tagged source=auto + region + year. Returns (count_upserted, error|None).

    Keeps existing MANUAL holidays untouched. Replaces prior AUTO holidays for the
    same (region,year) so a refresh reflects the latest official list.
    """
    if not region:
        region = (await get_region_setting())["region"]
    cfg = REGIONS.get(region, REGIONS[DEFAULT_REGION])
    country = cfg["country"]
    county = cfg["county"]

    url = f"{NAGER_BASE}/{year}/{country}"
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url)
        if resp.status_code != 200:
            return 0, f"Holiday service returned HTTP {resp.status_code}. Existing holidays kept — try again later."
        data = resp.json()
    except Exception as e:
        logger.warning(f"[holidays] fetch failed: {e}")
        return 0, f"Couldn't reach the holiday service ({e}). Existing holidays kept — try again or add manually."

    applicable = [h for h in data if _applies_to_region(h, county)]
    if not applicable:
        return 0, "No holidays returned for that region/year."

    # Remove previously auto-loaded holidays for this region+year, then insert fresh.
    try:
        await holidays_collection.delete_many({"source": "auto", "region": region, "holiday_year": year})
    except Exception:
        pass

    count = 0
    for h in applicable:
        try:
            d = datetime.strptime(h["date"], "%Y-%m-%d")
        except Exception:
            continue
        name = h.get("localName") or h.get("name") or "Public Holiday"
        doc = {
            "name": name,
            "date": d,
            "description": "Public holiday" + (f" · {region.split('-')[-1]}" if county else " · National"),
            "source": "auto",
            "region": region,
            "holiday_year": year,
            "is_public_holiday": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await holidays_collection.insert_one(doc)
        count += 1

    return count, None
