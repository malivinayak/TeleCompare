#!/usr/bin/env python3
"""
scripts/validate_plans.py
=========================
Validates data/plans.json before it is committed.
Exits with code 1 on any structural or data error, failing the workflow.
"""

import json
import sys
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

REPO_ROOT  = Path(__file__).resolve().parent.parent
PLANS_FILE = REPO_ROOT / "data" / "plans.json"

VALID_OPERATORS   = {"Jio", "Airtel", "Vi", "BSNL"}
VALID_STATUSES    = {"fresh", "fallback", "manual"}
REQUIRED_TOP_KEYS = {"lastUpdated", "dataStatus", "sourceNote", "sources", "plans"}
REQUIRED_PLAN_KEYS = {
    "id", "operator", "circle", "price", "validityDays",
    "dataPerDayGB", "totalDataGB", "unlimitedCalling",
    "smsPerDay", "has5G", "ottBenefits", "planType",
    "tags", "sourceUrl",
}

errors   = []
warnings = []


def fail(msg: str) -> None:
    errors.append(msg)
    log.error(msg)


def warn(msg: str) -> None:
    warnings.append(msg)
    log.warning(msg)


def validate_payload_structure(payload: dict) -> None:
    missing = REQUIRED_TOP_KEYS - set(payload.keys())
    if missing:
        fail(f"Top-level keys missing: {missing}")

    if not isinstance(payload.get("plans"), list):
        fail("'plans' must be a list.")

    if not isinstance(payload.get("sources"), list):
        fail("'sources' must be a list.")

    status = payload.get("dataStatus", "")
    if status not in VALID_STATUSES:
        fail(f"'dataStatus' must be one of {VALID_STATUSES}, got: {repr(status)}")

    if not payload.get("lastUpdated"):
        fail("'lastUpdated' is empty or missing.")


def validate_plan_fields(plan: dict, index: int) -> None:
    plan_id = plan.get("id", f"[index {index}]")
    missing = REQUIRED_PLAN_KEYS - set(plan.keys())
    if missing:
        fail(f"Plan '{plan_id}': missing required fields: {missing}")


def validate_numeric_values(plan: dict, index: int) -> None:
    plan_id = plan.get("id", f"[index {index}]")

    price = plan.get("price")
    if not isinstance(price, (int, float)) or price <= 0:
        fail(f"Plan '{plan_id}': 'price' must be a positive number, got {repr(price)}")

    validity = plan.get("validityDays")
    if not isinstance(validity, int) or validity <= 0:
        fail(f"Plan '{plan_id}': 'validityDays' must be a positive integer, got {repr(validity)}")

    dpd = plan.get("dataPerDayGB")
    if not isinstance(dpd, (int, float)) or dpd < 0:
        fail(f"Plan '{plan_id}': 'dataPerDayGB' must be >= 0, got {repr(dpd)}")

    total = plan.get("totalDataGB")
    if not isinstance(total, (int, float)) or total < 0:
        fail(f"Plan '{plan_id}': 'totalDataGB' must be >= 0, got {repr(total)}")

    sms = plan.get("smsPerDay")
    if sms is not None and (not isinstance(sms, int) or sms < 0):
        warn(f"Plan '{plan_id}': 'smsPerDay' should be a non-negative integer, got {repr(sms)}")

    # Sanity: totalDataGB should roughly equal dataPerDayGB × validityDays
    if isinstance(dpd, (int, float)) and isinstance(validity, int) and isinstance(total, (int, float)):
        expected = round(dpd * validity, 1)
        if total > 0 and abs(total - expected) > max(5, expected * 0.15):
            warn(f"Plan '{plan_id}': totalDataGB={total} seems inconsistent "
                 f"with dataPerDayGB={dpd} × validityDays={validity} ({expected} expected).")


def validate_operator_names(plan: dict, index: int) -> None:
    plan_id  = plan.get("id", f"[index {index}]")
    operator = plan.get("operator", "")
    if operator not in VALID_OPERATORS:
        fail(f"Plan '{plan_id}': unknown operator '{operator}'. "
             f"Valid: {VALID_OPERATORS}. Add to VALID_OPERATORS if intentional.")


def validate_unique_ids(plans: list) -> None:
    seen = {}
    for i, plan in enumerate(plans):
        pid = plan.get("id")
        if not pid:
            fail(f"Plan at index {i} has no 'id'.")
            continue
        if pid in seen:
            fail(f"Duplicate plan id '{pid}' at indices {seen[pid]} and {i}.")
        seen[pid] = i


def main() -> int:
    log.info("=== TeleCompare plan validation starting ===")

    if not PLANS_FILE.exists():
        log.error(f"plans.json not found at {PLANS_FILE}")
        return 1

    # ── Parse JSON ──────────────────────────────────────────────────────────
    try:
        with open(PLANS_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except json.JSONDecodeError as e:
        log.error(f"plans.json is not valid JSON: {e}")
        return 1

    # ── Structural checks ────────────────────────────────────────────────────
    validate_payload_structure(payload)
    if errors:
        log.error(f"Validation failed with {len(errors)} error(s). Aborting.")
        return 1

    plans = payload.get("plans", [])
    if not plans:
        fail("'plans' list is empty — refusing to commit an empty dataset.")
        return 1

    log.info(f"Validating {len(plans)} plan(s)...")

    # ── Per-plan checks ──────────────────────────────────────────────────────
    for i, plan in enumerate(plans):
        validate_plan_fields(plan, i)
        validate_numeric_values(plan, i)
        validate_operator_names(plan, i)

    # ── Cross-plan checks ────────────────────────────────────────────────────
    validate_unique_ids(plans)

    # ── Report ───────────────────────────────────────────────────────────────
    if warnings:
        log.warning(f"{len(warnings)} warning(s) — review above.")

    if errors:
        log.error(f"Validation FAILED: {len(errors)} error(s). plans.json will NOT be committed.")
        return 1

    log.info(f"Validation PASSED. {len(plans)} valid plans. "
             f"dataStatus={payload.get('dataStatus')}.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
