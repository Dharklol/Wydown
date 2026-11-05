"""Public synthetic guard tests; no market observations or performance metrics."""
import dataclasses
import unittest
from research_contract import ContractError, ResearchRun, Signal, epoch_nanoseconds, validate_signal_against_run

H = "sha256:" + "0" * 64


def run(**change):
    defaults = dict(contract_version=1, run_id="synthetic_run", spec_id="TREND-01",
                    spec_version="v1.0", code_revision="mock123", config_digest=H,
                    dataset_snapshot_digests=(H,), evaluation_split="engineering",
                    research_only=True, input_coverage_status="READY",
                    created_at_utc="2026-01-01T00:00:00Z", seed=20261105)
    return ResearchRun(**(defaults | change))


def sig(**change):
    defaults = dict(contract_version=1, run_id="synthetic_run", spec_id="TREND-01",
                    instrument_id="SYN:ETF:ONE", as_of_utc="2026-01-05T21:00:00Z",
                    available_at_utc="2026-01-05T21:00:00.000000001Z",
                    earliest_trade_at_utc="2026-01-06T14:30:00Z",
                    score="1", target_weight="0.25", reason="Synthetic interface test",
                    input_snapshot_ids=("synthetic_snapshot",))
    return Signal(**(defaults | change))


class ContractTests(unittest.TestCase):
    def test_preserve_nanos(self):
        a = epoch_nanoseconds("2026-01-01T00:00:00.000000001Z")
        b = epoch_nanoseconds("2026-01-01T00:00:00.000000002Z")
        self.assertEqual(b-a, 1)

    def test_date_and_timezone(self):
        for s in ("2026-02-31T00:00:00Z", "2026-01-01T00:00:00-06:00"):
            with self.assertRaises(ContractError):
                epoch_nanoseconds(s)

    def test_manifest_determinism(self):
        self.assertEqual(run().digest(), run().digest())
        self.assertNotEqual(run(seed=1).digest(), run(seed=2).digest())

    def test_immutable_signal(self):
        with self.assertRaises(dataclasses.FrozenInstanceError):
            sig().target_weight = "0.4"

    def test_no_close_fill_or_future_leak(self):
        with self.assertRaises(ContractError):
            sig(earliest_trade_at_utc="2026-01-05T21:00:00Z")
        with self.assertRaises(ContractError):
            sig(available_at_utc="2026-01-06T14:30:00Z")

    def test_prohibit_live(self):
        with self.assertRaises(ContractError):
            run(research_only=False)

    def test_provenance(self):
        with self.assertRaises(ContractError):
            run(dataset_snapshot_digests=())
        with self.assertRaises(ContractError):
            sig(input_snapshot_ids=())

    def test_long_only_and_pair_permissions(self):
        with self.assertRaises(ContractError):
            sig(target_weight="-0.1")
        with self.assertRaises(ContractError):
            sig(spec_id="PAIR-01", target_weight="-0.025")
        self.assertEqual(sig(spec_id="PAIR-01", pair_id="SYN:P1",
                             leg="short", target_weight="-0.025").leg, "short")

    def test_invalid_numbers(self):
        for value in ("NaN", "1e3", 0.1, float("nan")):
            with self.assertRaises(ContractError):
                sig(target_weight=value)

    def test_reserved_block_is_locked(self):
        with self.assertRaisesRegex(ContractError, "reserved block locked"):
            run(evaluation_split="reserved")

    def test_verified_coverage_required(self):
        with self.assertRaises(ContractError):
            validate_signal_against_run(sig(), run(input_coverage_status="UNVERIFIED"))
        validate_signal_against_run(sig(), run())


if __name__ == "__main__":
    unittest.main()
