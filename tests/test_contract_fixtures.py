"""Independent exact-decimal reference checks for Wydown Stage 1 fixtures.

NOT production accounting, a JSON Schema implementation, or a live trading test.
The Stage 2 OCaml kernel must independently satisfy these reference outcomes.
"""

from collections import defaultdict
from datetime import datetime
from decimal import Decimal
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/golden/scenarios-v1.json"
SCHEMA = ROOT / "schemas/canonical-event-v1.schema.json"

REQUIRED = {
    "schema_version", "event_id", "event_type", "environment",
    "account_id", "source_system", "source_event_id", "producer_version",
    "correlation_id", "event_time", "observed_at", "ingested_at", "payload",
}

EXPECTED_CASES = {
    "equity_buy_fee",
    "partial_duplicate",
    "long_put_expired",
    "cancel_replace",
    "broker_bust",
    "late_mark",
}


def decimal(value: str) -> Decimal:
    if not isinstance(value, str):
        raise ValueError("exact financial amounts must be decimal strings")
    if "e" in value.lower() or value.startswith("+"):
        raise ValueError("exponents and plus signs are disallowed")
    out = Decimal(value)
    if not out.is_finite() or out.as_tuple().exponent < -6:
        raise ValueError("nonfinite or overprecision")
    return out


def time(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("non-UTC timestamp")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def reference_projection(scenario: dict, registry: dict) -> dict:
    """Very small independent fixture oracle, not an OMS or live ledger."""
    cash = decimal(scenario["starting_cash"])
    quantities = defaultdict(Decimal)
    marks = {}
    active_orders = set()
    fills = {}
    ids = {}
    origin_ids = {}
    fee_total = Decimal(0)
    duplicates = 0
    for item in scenario["events"]:
        event_id = item["event_id"]
        origin = (
            item["environment"], item["account_id"],
            item["source_system"], item["source_event_id"],
        )
        encoded = json.dumps(item, sort_keys=True)
        if event_id in ids or origin in origin_ids:
            if ids.get(event_id) != encoded or origin_ids.get(origin) != encoded:
                raise ValueError("conflicting idempotency identity")
            duplicates += 1
            continue
        ids[event_id] = encoded
        origin_ids[origin] = encoded

        event_type = item["event_type"]
        payload = item["payload"]
        if event_type == "execution.fill":
            instrument = payload["instrument_id"]
            multiple = decimal(registry[instrument].get("premium_multiplier", "1"))
            qty = decimal(payload["quantity"])
            price = decimal(payload["price"])
            fee = decimal(payload["fee"])
            if payload["side"] != "buy":
                raise ValueError("this reference oracle only models buy-side fixtures")
            amount = qty * price * multiple
            cash -= amount + fee
            fee_total += fee
            quantities[instrument] += qty
            fills[payload["execution_id"]] = (instrument, qty, amount, fee)
        elif event_type == "execution.bust":
            instrument, qty, amount, fee = fills.pop(payload["original_execution_id"])
            quantities[instrument] -= qty
            cash += amount + fee
            fee_total -= fee
        elif event_type == "market.mark":
            instrument = payload["instrument_id"]
            if time(item["ingested_at"]) > time(scenario["as_of"]):
                continue
            candidate = (time(item["event_time"]), decimal(payload["price"]))
            if instrument not in marks or candidate[0] > marks[instrument][0]:
                marks[instrument] = candidate
        elif event_type == "option.expired":
            instrument = payload["instrument_id"]
            quantities[instrument] -= decimal(payload["quantity"])
            if quantities[instrument] < 0:
                raise ValueError("cannot expire absent contracts")
        elif event_type == "order.accepted":
            active_orders.add(payload["order_id"])
        elif event_type == "order.canceled":
            active_orders.remove(payload["order_id"])
        else:
            raise ValueError(f"unhandled fixture event: {event_type}")

    active_positions = {name: str(qty) for name, qty in quantities.items() if qty}
    value = cash
    for instrument, qty in quantities.items():
        if qty:
            if instrument not in marks:
                raise ValueError("position is unpriced; cannot produce NAV")
            multiple = decimal(registry[instrument].get("premium_multiplier", "1"))
            value += qty * marks[instrument][1] * multiple

    return {
        "cash": str(cash),
        "positions": active_positions,
        "nav": str(value),
        "fee_total": str(fee_total),
        "duplicate_events": duplicates,
        "working_orders": sorted(active_orders),
        "marks": {name: str(data[1]) for name, data in marks.items()},
    }


class CanonicalContractFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(FIXTURES.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))

    def test_schema_and_case_catalog(self):
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(self.source["fixture_version"], 1)
        self.assertEqual(
            {case["scenario_id"] for case in self.source["scenarios"]},
            EXPECTED_CASES,
        )
        self.assertEqual(self.source["base_currency"], "USD")

    def test_wire_envelopes_and_identity(self):
        known_types = set(self.schema["properties"]["event_type"]["enum"])
        registry = {i["instrument_id"] for i in self.source["registry"]}
        for scenario in self.source["scenarios"]:
            seen = {}
            for item in scenario["events"]:
                with self.subTest(scenario=scenario["scenario_id"], id=item["event_id"]):
                    self.assertTrue(REQUIRED <= set(item))
                    self.assertEqual(item["schema_version"], 1)
                    self.assertEqual(item["environment"], "paper")
                    self.assertIn(item["event_type"], known_types)
                    self.assertLessEqual(time(item["event_time"]), time(item["observed_at"]))
                    self.assertLessEqual(time(item["observed_at"]), time(item["ingested_at"]))
                    self.assertNotIn("broker_token", item)
                    if "instrument_id" in item["payload"]:
                        self.assertIn(item["payload"]["instrument_id"], registry)
                    if item["event_id"] in seen:
                        self.assertEqual(seen[item["event_id"]], item)
                    seen[item["event_id"]] = item

    def test_exact_decimal_wire_values(self):
        for scenario in self.source["scenarios"]:
            decimal(scenario["starting_cash"])
            decimal(scenario["expected"]["cash"])
            decimal(scenario["expected"]["nav"])
            for item in scenario["events"]:
                payload = item["payload"]
                for field in ("quantity", "price", "fee", "limit_price"):
                    if field in payload:
                        decimal(payload[field])

    def test_reference_outcomes(self):
        registry = {i["instrument_id"]: i for i in self.source["registry"]}
        for scenario in self.source["scenarios"]:
            with self.subTest(scenario=scenario["scenario_id"]):
                actual = reference_projection(scenario, registry)
                expected = scenario["expected"]
                for field in expected:
                    if field in {"cash", "nav", "fee_total"}:
                        self.assertEqual(decimal(actual[field]), decimal(expected[field]))
                    elif field in {"positions", "marks"}:
                        self.assertEqual(
                            {k: decimal(v) for k, v in actual[field].items()},
                            {k: decimal(v) for k, v in expected[field].items()},
                        )
                    else:
                        self.assertEqual(actual[field], expected[field])


if __name__ == "__main__":
    unittest.main()
