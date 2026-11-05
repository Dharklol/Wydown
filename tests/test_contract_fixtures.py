"""Synthetic Stage-1 contract oracle: NOT an execution engine or schema validator.

Uses Python Decimal independently of the planned OCaml Zarith/int64 implementation.
Only declared fixture event families are supported. Unknown cases fail closed.
"""

from collections import defaultdict, deque
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN, localcontext
import json
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "fixtures/golden/scenarios-v1.json"
SCHEMA = ROOT / "schemas/canonical-event-v1.schema.json"
MICRO_USD = Decimal("0.000001")
NANO_UNIT = Decimal("0.000000001")
UNIT_PRICE_DISPLAY = Decimal("0.000000000001")
DECIMAL_RE = re.compile(r"^-?(?:0|[1-9][0-9]*)(?:\.[0-9]{1,6})?$")
REQUIRED = {
    "schema_version", "event_id", "event_type", "environment",
    "account_id", "source_system", "source_event_id", "producer_version",
    "correlation_id", "event_time", "observed_at", "ingested_at", "payload",
}
EXPECTED_CASES = {
    "equity_buy_fee", "partial_duplicate", "long_put_expired", "cancel_replace",
    "broker_bust", "late_mark", "equity_sell_fifo", "fractional_rounding",
    "external_midrun_unav",
}


def decimal(text: str) -> Decimal:
    if not isinstance(text, str) or not DECIMAL_RE.fullmatch(text):
        raise ValueError("invalid canonical decimal string (<=6 places)")
    result = Decimal(text)
    if not result.is_finite():
        raise ValueError("invalid numeric value")
    return result


def usd(value: Decimal) -> Decimal:
    return value.quantize(MICRO_USD, rounding=ROUND_HALF_EVEN)


def timestamp(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("non-UTC timestamp")
    # Stage-1 fixture timestamps are second precision. Nanosecond handling is
    # a deferred implementation test; Python datetime only retains microseconds.
    if "." in value:
        raise ValueError("reference fixture timestamps must be whole seconds")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def economic_signature(item: dict) -> str:
    """Transport/receipt metadata must not affect economic idempotency."""
    stable = {
        key: item[key] for key in (
            "event_type", "environment", "account_id", "source_system",
            "source_event_id", "event_time", "payload",
        )
    }
    if "source_sequence" in item:
        stable["source_sequence"] = item["source_sequence"]
    return json.dumps(stable, sort_keys=True, separators=(",", ":"))


def reference_projection(scenario: dict, registry: dict) -> dict:
    """Small exact-decimal, balanced-posting oracle for design fixtures."""
    with localcontext() as ctx:
        ctx.prec = 60
        cash = Decimal(0)
        positions = defaultdict(Decimal)
        lots = defaultdict(deque)  # Each lot: [remaining_quantity, remaining_cost].
        marks = defaultdict(list)
        working = set()
        accepted_source = {}
        accepted_ids = {}
        fill_history = {}
        debit_credit = []
        fees = Decimal(0)
        realized = Decimal(0)
        flow_total = Decimal(0)
        units = Decimal(0)
        duplicate_count = 0
        valuation_time = timestamp(scenario["valuation_time"])
        knowledge_cutoff = timestamp(scenario["knowledge_cutoff"])

        def post(entries):
            if sum((amount for _, amount in entries), Decimal(0)) != 0:
                raise AssertionError("unbalanced accounting posting")
            debit_credit.append(entries)

        def current_marks(at, known):
            selected = {}
            for instr, candidates in marks.items():
                eligible = [
                    (event_time, price)
                    for event_time, ingested, price in candidates
                    if event_time <= at and ingested <= known
                ]
                if eligible:
                    selected[instr] = max(eligible, key=lambda x: x[0])[1]
            return selected

        def nav(at, known):
            selected = current_marks(at, known)
            value = cash
            for instr, quantity in positions.items():
                if quantity != 0:
                    if instr not in selected:
                        raise ValueError(f"UNPRICED position: {instr}")
                    mult = decimal(registry[instr].get("premium_multiplier", "1"))
                    value += usd(quantity * mult * selected[instr])
            return value

        # Journal order is ingested order; the fully specified accounting
        # replay/ordering policy is the OCaml Stage-2 responsibility.
        for item in scenario["events"]:
            source_key = (
                item["environment"], item["account_id"],
                item["source_system"], item["source_event_id"],
            )
            sig = economic_signature(item)
            event_id = item["event_id"]
            if event_id in accepted_ids and accepted_ids[event_id] != sig:
                raise ValueError("conflicting canonical event ID")
            if source_key in accepted_source:
                if accepted_source[source_key] != sig:
                    raise ValueError("conflicting economic source ID")
                duplicate_count += 1
                continue
            accepted_ids[event_id] = sig
            accepted_source[source_key] = sig

            typ = item["event_type"]
            p = item["payload"]
            event_time = timestamp(item["event_time"])
            known_time = timestamp(item["ingested_at"])
            if event_time > valuation_time or known_time > knowledge_cutoff:
                # An ineligible fact may be in the journal, but is not in
                # this as-of account state. It can be replayed at a later T/K.
                continue

            if typ == "cash.flow":
                amount = usd(decimal(p["amount"]))
                if amount <= 0 or p["external"] is not True:
                    raise ValueError("invalid external cash movement")
                delta = amount if p["flow_type"] == "deposit" else -amount
                if units == 0:
                    if delta <= 0 or cash != 0:
                        raise ValueError("initial funding must be positive")
                    unit_price = Decimal(1)
                else:
                    pre_flow_nav = nav(event_time, known_time)
                    unit_price = pre_flow_nav / units
                    if unit_price <= 0:
                        raise ValueError("invalid pre-flow unit price")
                change_units = (delta / unit_price).quantize(
                    NANO_UNIT, rounding=ROUND_HALF_EVEN
                )
                if units + change_units <= 0 or cash + delta < 0:
                    raise ValueError("invalid subscription or withdrawal")
                units += change_units
                cash += delta
                flow_total += delta
                post([("cash", delta), ("contributed_capital", -delta)])

            elif typ == "execution.fill":
                instrument = p["instrument_id"]
                mult = decimal(registry[instrument].get("premium_multiplier", "1"))
                qty = decimal(p["quantity"])
                price = decimal(p["price"])
                fee = usd(decimal(p["fee"]))
                if qty <= 0 or price <= 0 or fee < 0:
                    raise ValueError("invalid fill amount")
                gross = usd(qty * mult * price)
                execution_id = p["execution_id"]
                if execution_id in fill_history:
                    raise ValueError("duplicate broker execution with fresh source ID")
                if p["side"] == "buy":
                    cash -= gross + fee
                    positions[instrument] += qty
                    lot = [qty, gross, execution_id]
                    lots[instrument].append(lot)
                    postings = [
                        ("investment_cost", gross), ("fee_expense", fee),
                        ("cash", -(gross + fee)),
                    ]
                    fill_history[execution_id] = (p, gross, fee, postings, lot)
                elif p["side"] == "sell":
                    if positions[instrument] < qty:
                        raise ValueError("cannot sell unowned units in sell event")
                    needed = qty
                    basis = Decimal(0)
                    while needed:
                        if not lots[instrument]:
                            raise ValueError("FIFO cost basis absent")
                        lot = lots[instrument][0]
                        take = min(needed, lot[0])
                        allocated = lot[1] if take == lot[0] else usd(lot[1] * take / lot[0])
                        lot[0] -= take
                        lot[1] -= allocated
                        basis += allocated
                        needed -= take
                        if lot[0] == 0:
                            lots[instrument].popleft()
                    positions[instrument] -= qty
                    cash += gross - fee
                    realized += gross - basis
                    postings = [
                        ("cash", gross - fee), ("fee_expense", fee),
                        ("investment_cost", -basis), ("realized_pnl", -(gross - basis)),
                    ]
                    fill_history[execution_id] = (p, gross, fee, postings, None)
                else:
                    raise ValueError("unsupported short-side fixture; research only")
                fees += fee
                post(postings)

            elif typ == "execution.bust":
                p0, gross, fee, original_postings, lot = fill_history.pop(
                    p["original_execution_id"]
                )
                instr = p0["instrument_id"]
                if p0["side"] != "buy" or lot is None:
                    raise ValueError("complex bust requires full replay/correction")
                if lot not in lots[instr] or lot[0] != decimal(p0["quantity"]):
                    raise ValueError("bust affects consumed lot; must replay")
                lots[instr].remove(lot)
                positions[instr] -= decimal(p0["quantity"])
                cash += gross + fee
                fees -= fee
                post([(account, -amount) for account, amount in original_postings])

            elif typ == "option.expired":
                instr = p["instrument_id"]
                qty = decimal(p["quantity"])
                if qty <= 0 or qty != positions[instr]:
                    raise ValueError("unsupported partial or uncovered expiration")
                basis = sum((lot[1] for lot in lots[instr]), Decimal(0))
                positions[instr] -= qty
                lots[instr].clear()
                realized -= basis
                post([("realized_pnl", basis), ("investment_cost", -basis)])

            elif typ == "market.mark":
                instr = p["instrument_id"]
                marks[instr].append((event_time, known_time, decimal(p["price"])))

            elif typ == "order.accepted":
                if p["order_id"] in working:
                    raise ValueError("duplicate working order")
                working.add(p["order_id"])

            elif typ == "order.canceled":
                if p["order_id"] not in working:
                    raise ValueError("cancel unknown order")
                working.remove(p["order_id"])

            else:
                raise ValueError(f"unsupported event type: {typ}")

        value = nav(valuation_time, knowledge_cutoff)
        current = current_marks(valuation_time, knowledge_cutoff)
        unrealized = Decimal(0)
        for instr, qty in positions.items():
            if qty:
                mult = decimal(registry[instr].get("premium_multiplier", "1"))
                market_value = usd(qty * mult * current[instr])
                basis = sum((lot[1] for lot in lots[instr]), Decimal(0))
                unrealized += market_value - basis
        if usd(value - flow_total) != usd(realized + unrealized - fees):
            raise AssertionError("P&L does not reconcile with NAV and flows")
        if units <= 0:
            raise ValueError("UNAV unit supply absent")

        return {
            "cash": cash,
            "positions": {k: v for k, v in positions.items() if v},
            "nav": value,
            "fee_total": fees,
            "duplicate_events": duplicate_count,
            "working_orders": sorted(working),
            "marks": current,
            "external_net_flow": flow_total,
            "unit_supply": units,
            "unit_price": (value / units).quantize(
                UNIT_PRICE_DISPLAY, rounding=ROUND_HALF_EVEN
            ),
            "realized_trading_pnl": realized,
            "unrealized_trading_pnl": unrealized,
            "net_investment_pnl": value - flow_total,
            "posting_transactions": len(debit_credit),
        }


class CanonicalContractFixtureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = json.loads(FIXTURES.read_text(encoding="utf-8"))
        cls.schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
        cls.registry = {
            instrument["instrument_id"]: instrument
            for instrument in cls.source["registry"]
        }

    def test_schema_and_case_catalog(self):
        self.assertEqual(self.schema["properties"]["schema_version"]["const"], 1)
        self.assertEqual(self.source["fixture_version"], 1)
        self.assertEqual(
            {case["scenario_id"] for case in self.source["scenarios"]},
            EXPECTED_CASES,
        )

    def test_wire_envelopes(self):
        known = set(self.schema["properties"]["event_type"]["enum"])
        for case in self.source["scenarios"]:
            for ev in case["events"]:
                with self.subTest(case=case["scenario_id"], event=ev["event_id"]):
                    self.assertTrue(REQUIRED <= ev.keys())
                    self.assertEqual(ev["schema_version"], 1)
                    self.assertEqual(ev["environment"], "paper")
                    self.assertIn(ev["event_type"], known)
                    self.assertLessEqual(timestamp(ev["event_time"]), timestamp(ev["observed_at"]))
                    self.assertLessEqual(timestamp(ev["observed_at"]), timestamp(ev["ingested_at"]))
                    if "instrument_id" in ev["payload"]:
                        self.assertIn(ev["payload"]["instrument_id"], self.registry)

    def test_exact_wire_values(self):
        for case in self.source["scenarios"]:
            for ev in case["events"]:
                for key in ("amount", "quantity", "price", "fee", "limit_price"):
                    if key in ev["payload"]:
                        self.assertGreaterEqual(decimal(ev["payload"][key]), 0)

    def test_all_cases_journal_funded(self):
        for case in self.source["scenarios"]:
            self.assertNotIn("starting_cash", case)
            self.assertEqual(case["events"][0]["event_type"], "cash.flow")
            self.assertEqual(case["events"][0]["payload"]["amount"], "5000.00")

    def test_reference_outcomes_and_balanced_postings(self):
        numeric_fields = {
            "cash", "nav", "fee_total", "external_net_flow",
            "unit_supply", "unit_price", "realized_trading_pnl",
            "unrealized_trading_pnl", "net_investment_pnl",
        }
        for case in self.source["scenarios"]:
            with self.subTest(case=case["scenario_id"]):
                actual = reference_projection(case, self.registry)
                for field, expected in case["expected"].items():
                    if field in numeric_fields:
                        self.assertEqual(actual[field], decimal(expected), field)
                    elif field in {"positions", "marks"}:
                        self.assertEqual(
                            actual[field],
                            {k: decimal(v) for k, v in expected.items()},
                            field,
                        )
                    else:
                        self.assertEqual(actual[field], expected, field)
                self.assertGreater(actual["posting_transactions"], 0)

    def test_redelivery_ignores_transport_metadata(self):
        case = next(c for c in self.source["scenarios"]
                    if c["scenario_id"] == "partial_duplicate")
        fills = [ev for ev in case["events"] if ev["event_type"] == "execution.fill"]
        self.assertEqual(len(fills), 3)
        self.assertNotEqual(fills[1]["event_id"], fills[2]["event_id"])
        self.assertNotEqual(fills[1]["ingested_at"], fills[2]["ingested_at"])
        self.assertEqual(economic_signature(fills[1]), economic_signature(fills[2]))

    def test_conflicting_source_event_is_rejected(self):
        case = next(c for c in self.source["scenarios"]
                    if c["scenario_id"] == "partial_duplicate")
        changed = json.loads(json.dumps(case))
        # Conflict with identical source identity must not be treated as a retry.
        events = [ev for ev in changed["events"] if ev["event_type"] == "execution.fill"]
        events[2]["payload"]["price"] = "101.00"
        with self.assertRaisesRegex(ValueError, "conflicting economic source ID"):
            reference_projection(changed, self.registry)

    def test_decimal_rejections_and_midpoint_rounding(self):
        for bad in ("NaN", "Infinity", "1e2", "+2", "0.1234567", "00.10"):
            with self.subTest(value=bad):
                with self.assertRaises(ValueError):
                    decimal(bad)
        self.assertEqual(usd(decimal("0.000002") / 4), Decimal("0.000000"))
        self.assertEqual(usd(decimal("0.000006") / 4), Decimal("0.000002"))
        self.assertEqual(
            usd(decimal("0.000001") * decimal("123.456789")),
            Decimal("0.000123"),
        )

    def test_unitized_flow_is_not_return(self):
        case = next(c for c in self.source["scenarios"]
                    if c["scenario_id"] == "external_midrun_unav")
        result = reference_projection(case, self.registry)
        self.assertEqual(result["unit_supply"], Decimal("6000"))
        self.assertEqual(result["unit_price"], Decimal("1.03"))
        self.assertEqual(result["net_investment_pnl"], Decimal("160"))


if __name__ == "__main__":
    unittest.main()
