#!/usr/bin/env python3
"""
scripts/update_plans.py
=======================
Fetches Indian telecom prepaid plan data, normalises it into a consistent
schema, and writes data/plans.json.

Strategy (honest about limitations):
- PRIMARY: Attempt to fetch from public/demo API endpoints if configured.
- FALLBACK: If live fetch fails or no API is configured, preserve the
  existing plans.json so the site always has valid data.
- ALWAYS: Add/update lastUpdated, dataStatus, sourceNote fields.

To add a real API key later:
  1. Add the secret in GitHub → Settings → Secrets → Actions.
  2. Reference it in the workflow env: MY_API_KEY: ${{ secrets.MY_API_KEY }}
  3. Use os.environ.get("MY_API_KEY") here. Never hard-code secrets.
"""

import json
import os
import sys
import copy
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path

# ── Optional: requests for HTTP fetching ──────────────────────────────────────
try:
    import requests
    HAS_REQUESTS = True
except ImportError:
    HAS_REQUESTS = False

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

# ── Paths ──────────────────────────────────────────────────────────────────────
REPO_ROOT   = Path(__file__).resolve().parent.parent
PLANS_FILE  = REPO_ROOT / "data" / "plans.json"

# ── IST timezone offset ────────────────────────────────────────────────────────
IST = timezone(timedelta(hours=5, minutes=30))

# ── Seed / fallback data ───────────────────────────────────────────────────────
# This is the authoritative hand-maintained seed. It is used when no live
# source is available. Keep it up to date manually when prices change.
SEED_PLANS = [
    # ── JIO ──────────────────────────────────────────────────────────────────
    {
        "id": "jio-199-28d", "operator": "Jio", "circle": "All India",
        "price": 199, "validityDays": 28, "dataPerDayGB": 1.5, "totalDataGB": 42,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": False,
        "ottBenefits": [], "planType": "Prepaid",
        "tags": ["Budget", "Popular"],
        "sourceUrl": "https://www.jio.com/recharge", "notes": ""
    },
    {
        "id": "jio-299-28d", "operator": "Jio", "circle": "All India",
        "price": 299, "validityDays": 28, "dataPerDayGB": 2.0, "totalDataGB": 56,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": True,
        "ottBenefits": ["JioCinema", "JioTV"], "planType": "Prepaid",
        "tags": ["5G", "Popular"],
        "sourceUrl": "https://www.jio.com/recharge", "notes": ""
    },
    {
        "id": "jio-349-28d", "operator": "Jio", "circle": "All India",
        "price": 349, "validityDays": 28, "dataPerDayGB": 3.0, "totalDataGB": 84,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": True,
        "ottBenefits": ["JioCinema Premium", "JioTV", "Sony LIV"],
        "planType": "Prepaid", "tags": ["5G", "OTT", "High Data"],
        "sourceUrl": "https://www.jio.com/recharge", "notes": ""
    },
    {
        "id": "jio-719-84d", "operator": "Jio", "circle": "All India",
        "price": 719, "validityDays": 84, "dataPerDayGB": 2.0, "totalDataGB": 168,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": True,
        "ottBenefits": ["JioCinema", "JioTV"], "planType": "Prepaid",
        "tags": ["5G", "Long Validity", "Popular"],
        "sourceUrl": "https://www.jio.com/recharge", "notes": ""
    },
    {
        "id": "jio-899-84d", "operator": "Jio", "circle": "All India",
        "price": 899, "validityDays": 84, "dataPerDayGB": 3.0, "totalDataGB": 252,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": True,
        "ottBenefits": ["JioCinema Premium", "JioTV", "Sony LIV"],
        "planType": "Prepaid", "tags": ["5G", "OTT", "Long Validity"],
        "sourceUrl": "https://www.jio.com/recharge", "notes": ""
    },
    {
        "id": "jio-2999-365d", "operator": "Jio", "circle": "All India",
        "price": 2999, "validityDays": 365, "dataPerDayGB": 2.5, "totalDataGB": 730,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": True,
        "ottBenefits": ["JioCinema Premium", "JioTV"],
        "planType": "Prepaid", "tags": ["5G", "Annual"],
        "sourceUrl": "https://www.jio.com/recharge", "notes": ""
    },
    # ── AIRTEL ───────────────────────────────────────────────────────────────
    {
        "id": "airtel-179-28d", "operator": "Airtel", "circle": "All India",
        "price": 179, "validityDays": 28, "dataPerDayGB": 1.0, "totalDataGB": 28,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": False,
        "ottBenefits": [], "planType": "Prepaid", "tags": ["Budget"],
        "sourceUrl": "https://www.airtel.in/recharge-online", "notes": ""
    },
    {
        "id": "airtel-299-28d", "operator": "Airtel", "circle": "All India",
        "price": 299, "validityDays": 28, "dataPerDayGB": 1.5, "totalDataGB": 42,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": True,
        "ottBenefits": ["Airtel Xstream"], "planType": "Prepaid",
        "tags": ["5G", "Popular"],
        "sourceUrl": "https://www.airtel.in/recharge-online", "notes": ""
    },
    {
        "id": "airtel-359-28d", "operator": "Airtel", "circle": "All India",
        "price": 359, "validityDays": 28, "dataPerDayGB": 2.0, "totalDataGB": 56,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": True,
        "ottBenefits": ["Airtel Xstream", "Disney+ Hotstar"],
        "planType": "Prepaid", "tags": ["5G", "OTT", "Popular"],
        "sourceUrl": "https://www.airtel.in/recharge-online", "notes": ""
    },
    {
        "id": "airtel-699-84d", "operator": "Airtel", "circle": "All India",
        "price": 699, "validityDays": 84, "dataPerDayGB": 1.5, "totalDataGB": 126,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": True,
        "ottBenefits": ["Airtel Xstream"], "planType": "Prepaid",
        "tags": ["5G", "Long Validity", "Popular"],
        "sourceUrl": "https://www.airtel.in/recharge-online", "notes": ""
    },
    {
        "id": "airtel-859-84d", "operator": "Airtel", "circle": "All India",
        "price": 859, "validityDays": 84, "dataPerDayGB": 2.0, "totalDataGB": 168,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": True,
        "ottBenefits": ["Airtel Xstream", "Disney+ Hotstar"],
        "planType": "Prepaid", "tags": ["5G", "OTT", "Long Validity"],
        "sourceUrl": "https://www.airtel.in/recharge-online", "notes": ""
    },
    {
        "id": "airtel-3359-365d", "operator": "Airtel", "circle": "All India",
        "price": 3359, "validityDays": 365, "dataPerDayGB": 2.0, "totalDataGB": 730,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": True,
        "ottBenefits": ["Airtel Xstream", "Disney+ Hotstar"],
        "planType": "Prepaid", "tags": ["5G", "Annual", "OTT"],
        "sourceUrl": "https://www.airtel.in/recharge-online", "notes": ""
    },
    # ── VI ────────────────────────────────────────────────────────────────────
    {
        "id": "vi-179-28d", "operator": "Vi", "circle": "All India",
        "price": 179, "validityDays": 28, "dataPerDayGB": 1.0, "totalDataGB": 28,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": False,
        "ottBenefits": [], "planType": "Prepaid", "tags": ["Budget"],
        "sourceUrl": "https://www.myvi.in/prepaid/recharge-plans", "notes": ""
    },
    {
        "id": "vi-269-28d", "operator": "Vi", "circle": "All India",
        "price": 269, "validityDays": 28, "dataPerDayGB": 1.5, "totalDataGB": 42,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": False,
        "ottBenefits": ["Vi Movies & TV"], "planType": "Prepaid",
        "tags": ["Popular", "OTT"],
        "sourceUrl": "https://www.myvi.in/prepaid/recharge-plans", "notes": ""
    },
    {
        "id": "vi-649-84d", "operator": "Vi", "circle": "All India",
        "price": 649, "validityDays": 84, "dataPerDayGB": 1.5, "totalDataGB": 126,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": False,
        "ottBenefits": ["Vi Movies & TV"], "planType": "Prepaid",
        "tags": ["Long Validity"],
        "sourceUrl": "https://www.myvi.in/prepaid/recharge-plans", "notes": ""
    },
    {
        "id": "vi-2899-365d", "operator": "Vi", "circle": "All India",
        "price": 2899, "validityDays": 365, "dataPerDayGB": 1.5, "totalDataGB": 547,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": False,
        "ottBenefits": ["Vi Movies & TV"], "planType": "Prepaid",
        "tags": ["Annual"],
        "sourceUrl": "https://www.myvi.in/prepaid/recharge-plans", "notes": ""
    },
    # ── BSNL ──────────────────────────────────────────────────────────────────
    {
        "id": "bsnl-107-24d", "operator": "BSNL", "circle": "All India",
        "price": 107, "validityDays": 24, "dataPerDayGB": 1.0, "totalDataGB": 24,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": False,
        "ottBenefits": [], "planType": "Prepaid", "tags": ["Budget", "Cheapest"],
        "sourceUrl": "https://selfcare.bsnl.co.in",
        "notes": "Verify calling terms on BSNL portal — may vary by circle."
    },
    {
        "id": "bsnl-197-28d", "operator": "BSNL", "circle": "All India",
        "price": 197, "validityDays": 28, "dataPerDayGB": 2.0, "totalDataGB": 56,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": False,
        "ottBenefits": [], "planType": "Prepaid", "tags": ["Budget", "High Data"],
        "sourceUrl": "https://selfcare.bsnl.co.in", "notes": ""
    },
    {
        "id": "bsnl-797-90d", "operator": "BSNL", "circle": "All India",
        "price": 797, "validityDays": 90, "dataPerDayGB": 2.0, "totalDataGB": 180,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": False,
        "ottBenefits": [], "planType": "Prepaid", "tags": ["Budget", "Long Validity"],
        "sourceUrl": "https://selfcare.bsnl.co.in", "notes": ""
    },
    {
        "id": "bsnl-2399-365d", "operator": "BSNL", "circle": "All India",
        "price": 2399, "validityDays": 365, "dataPerDayGB": 2.0, "totalDataGB": 730,
        "unlimitedCalling": True, "smsPerDay": 100, "has5G": False,
        "ottBenefits": [], "planType": "Prepaid", "tags": ["Annual", "Budget"],
        "sourceUrl": "https://selfcare.bsnl.co.in", "notes": ""
    },
]


def load_existing_plans() -> dict:
    """Load the current plans.json, return empty payload on failure."""
    if not PLANS_FILE.exists():
        log.info("No existing plans.json found — will use seed data.")
        return {}
    try:
        with open(PLANS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        log.info(f"Loaded existing plans.json ({len(data.get('plans', []))} plans).")
        return data
    except Exception as e:
        log.warning(f"Could not parse existing plans.json: {e}")
        return {}


def fetch_plan_sources() -> list[dict]:
    """
    Attempt to fetch from live sources.

    Currently returns an empty list (no live source configured), so the
    pipeline falls back to seed data. When you add a real data source:

      Option A — RapidAPI / third-party:
        api_key = os.environ.get("RECHARGE_API_KEY")  # set via GitHub Secrets
        if not api_key:
            log.warning("RECHARGE_API_KEY not set — skipping live fetch.")
            return []
        resp = requests.get(
            "https://some-api.example.com/plans",
            headers={"X-Api-Key": api_key},
            timeout=20,
        )
        resp.raise_for_status()
        return resp.json().get("plans", [])

      Option B — HTML scraping (fragile — only if ToS permits):
        Use requests + BeautifulSoup to parse operator plan pages.
        Wrap in try/except and return [] on any failure.

    NEVER put API keys in this file or in any frontend file.
    Add them as GitHub repository secrets and pass via workflow env vars.
    """
    if not HAS_REQUESTS:
        log.info("requests not installed — skipping live fetch.")
        return []

    # Example: check for an optional API key in environment
    api_key = os.environ.get("RECHARGE_API_KEY", "")
    if not api_key:
        log.info("No RECHARGE_API_KEY configured — using seed data.")
        return []

    # Placeholder for a real API call when key is available
    try:
        log.info("Fetching from live API...")
        # resp = requests.get("https://api.example.com/india/prepaid-plans",
        #                     headers={"Authorization": f"Bearer {api_key}"},
        #                     timeout=20)
        # resp.raise_for_status()
        # raw = resp.json().get("plans", [])
        # return [normalize_plan(p) for p in raw]
        return []
    except Exception as e:
        log.warning(f"Live fetch failed: {e}")
        return []


def normalize_plan(raw: dict) -> dict:
    """
    Normalise an arbitrary plan dict into the canonical schema.
    Adjust field mappings to match your actual data source.
    """
    now_date = datetime.now(IST).strftime("%Y-%m-%d")
    return {
        "id":               str(raw.get("id", "")),
        "operator":         str(raw.get("operator", "")),
        "circle":           str(raw.get("circle", "All India")),
        "price":            float(raw.get("price", 0)),
        "validityDays":     int(raw.get("validityDays", raw.get("validity_days", 0))),
        "dataPerDayGB":     float(raw.get("dataPerDayGB", raw.get("data_per_day", 0))),
        "totalDataGB":      float(raw.get("totalDataGB", raw.get("total_data", 0))),
        "unlimitedCalling": bool(raw.get("unlimitedCalling", raw.get("unlimited_calling", True))),
        "smsPerDay":        int(raw.get("smsPerDay", raw.get("sms_per_day", 100))),
        "has5G":            bool(raw.get("has5G", raw.get("has_5g", False))),
        "ottBenefits":      list(raw.get("ottBenefits", raw.get("ott_benefits", []))),
        "planType":         str(raw.get("planType", "Prepaid")),
        "tags":             list(raw.get("tags", [])),
        "sourceUrl":        str(raw.get("sourceUrl", raw.get("source_url", ""))),
        "lastSeen":         str(raw.get("lastSeen", now_date)),
        "notes":            str(raw.get("notes", "")),
    }


def merge_and_dedupe_plans(live: list, seed: list) -> list:
    """
    Merge live-fetched plans with seed. Live plans take priority.
    Deduplication is by plan id.
    """
    merged = {p["id"]: p for p in seed}
    for p in live:
        merged[p["id"]] = p  # live overrides seed
    result = list(merged.values())
    result.sort(key=lambda p: (p["operator"], p["price"]))
    return result


def build_output_payload(plans: list, data_status: str, sources: list) -> dict:
    """Assemble the full plans.json payload."""
    now_iso = datetime.now(IST).isoformat(timespec="seconds")
    return {
        "lastUpdated": now_iso,
        "dataStatus":  data_status,
        "sourceNote":  (
            "Plans are periodically updated from public/operator/TRAI/API sources. "
            "Verify before recharge."
        ),
        "sources": sources,
        "plans": plans,
    }


def write_plans_json(payload: dict) -> None:
    """Write the payload to data/plans.json (pretty-printed)."""
    PLANS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PLANS_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    log.info(f"Written {len(payload['plans'])} plans to {PLANS_FILE}.")


def main() -> int:
    """
    Main pipeline. Returns exit code (0 = success, 1 = fatal error).
    """
    log.info("=== TeleCompare plan update pipeline starting ===")

    existing   = load_existing_plans()
    live_plans = fetch_plan_sources()
    now_iso    = datetime.now(IST).isoformat(timespec="seconds")

    if live_plans:
        log.info(f"Live fetch returned {len(live_plans)} plans.")
        plans       = merge_and_dedupe_plans(live_plans, SEED_PLANS)
        data_status = "fresh"
        sources     = [{"name": "Live API", "url": "", "fetchedAt": now_iso, "status": "success"}]
    else:
        log.info("No live data — using seed / existing plans.")
        # If we have existing valid plans, preserve them; otherwise use seed.
        existing_plans = existing.get("plans")
        if existing_plans:
            log.info(f"Preserving {len(existing_plans)} existing plans.")
            plans       = existing_plans
            data_status = "fallback"
        else:
            log.info("No existing plans found — using built-in seed data.")
            plans       = [normalize_plan(p) for p in SEED_PLANS]
            data_status = "manual"
        sources = [{"name": "Seed / manual data", "url": "", "fetchedAt": now_iso, "status": "fallback"}]

    payload = build_output_payload(plans, data_status, sources)
    write_plans_json(payload)

    log.info(f"Done. dataStatus={data_status}, plans={len(plans)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
