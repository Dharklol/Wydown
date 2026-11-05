"""Immutable research metadata and target signals: no brokerage or backtest logic."""
from __future__ import annotations
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal
import hashlib
import json
import re


class ContractError(ValueError):
    """A research record violates the frozen interface."""


UTC = re.compile(r"^(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?Z$")
NUM = re.compile(r"^-?(?:0|[1-9]\d*)(?:\.\d+)?$")
DIGEST = re.compile(r"^sha256:[a-f0-9]{64}$")
IDENT = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")
SPECS = frozenset(("TREND-01", "VQ-01", "MOM-01", "PAIR-01"))
SPLITS = frozenset(("engineering", "validation_1", "validation_2", "reserved",
                    "recent_diagnostic", "prospective_shadow"))


def epoch_nanoseconds(s: str) -> int:
    """Exact UTC timestamp comparison; preserve 9 digits, unlike datetime."""
    m = UTC.fullmatch(s) if isinstance(s, str) else None
    if m is None:
        raise ContractError("UTC timestamp must end Z, with <=9 fractional digits")
    try:
        dt = datetime.strptime(m[1], "%Y-%m-%dT%H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError as e:
        raise ContractError("invalid calendar timestamp") from e
    seconds = int((dt - datetime(1970, 1, 1, tzinfo=timezone.utc)).total_seconds())
    return seconds * 1_000_000_000 + int((m[2] or "0").ljust(9, "0"))


def decimal(s: str) -> Decimal:
    if not isinstance(s, str) or NUM.fullmatch(s) is None:
        raise ContractError("use exact finite decimal strings, never floats")
    return Decimal(s)


def check_id(value: str) -> None:
    if not isinstance(value, str) or IDENT.fullmatch(value) is None:
        raise ContractError("invalid stable identifier")


def check_digest(value: str) -> None:
    if not isinstance(value, str) or DIGEST.fullmatch(value) is None:
        raise ContractError("expected sha256 digest")


@dataclass(frozen=True, slots=True)
class ResearchRun:
    contract_version: int
    run_id: str
    spec_id: str
    spec_version: str
    code_revision: str
    config_digest: str
    dataset_snapshot_digests: tuple[str, ...]
    evaluation_split: str
    research_only: bool
    input_coverage_status: str
    created_at_utc: str
    seed: int

    def __post_init__(self):
        if self.contract_version != 1 or self.spec_id not in SPECS:
            raise ContractError("unsupported run spec/version")
        for x in (self.run_id, self.spec_version, self.code_revision):
            check_id(x)
        if self.evaluation_split not in SPLITS:
            raise ContractError("unknown chronological evaluation block")
        if self.research_only is not True:
            raise ContractError("research metadata can never authorize trading")
        if self.input_coverage_status not in ("UNVERIFIED", "DATA-BLOCKED", "READY"):
            raise ContractError("unknown data coverage state")
        check_digest(self.config_digest)
        if not self.dataset_snapshot_digests:
            raise ContractError("missing immutable data source snapshot")
        for x in self.dataset_snapshot_digests:
            check_digest(x)
        epoch_nanoseconds(self.created_at_utc)
        if type(self.seed) is not int or self.seed < 0:
            raise ContractError("invalid seed")

    def digest(self) -> str:
        payload = (json.dumps(asdict(self), sort_keys=True, separators=(",", ":"),
                              allow_nan=False) + "\n").encode("utf-8")
        return "sha256:" + hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True, slots=True)
class Signal:
    contract_version: int
    run_id: str
    spec_id: str
    instrument_id: str
    as_of_utc: str
    available_at_utc: str
    earliest_trade_at_utc: str
    score: str
    target_weight: str
    reason: str
    input_snapshot_ids: tuple[str, ...]
    pair_id: str | None = None
    leg: str | None = None

    def __post_init__(self):
        if self.contract_version != 1 or self.spec_id not in SPECS:
            raise ContractError("unsupported signal")
        check_id(self.run_id)
        check_id(self.instrument_id)
        if not isinstance(self.reason, str) or not 0 < len(self.reason) <= 256:
            raise ContractError("missing/invalid rationale")
        if not self.input_snapshot_ids:
            raise ContractError("missing point-in-time input references")
        for x in self.input_snapshot_ids:
            check_id(x)
        a = epoch_nanoseconds(self.as_of_utc)
        k = epoch_nanoseconds(self.available_at_utc)
        fill = epoch_nanoseconds(self.earliest_trade_at_utc)
        if not a <= k < fill:
            raise ContractError("trade cannot precede data availability")
        decimal(self.score)
        w = decimal(self.target_weight)
        if not Decimal(-1) <= w <= Decimal(1):
            raise ContractError("target outside signed unit weight bounds")
        if self.spec_id == "PAIR-01":
            if self.pair_id is None or self.leg not in ("long", "short"):
                raise ContractError("pairs require explicit pair and leg")
            check_id(self.pair_id)
            if (self.leg == "long" and w <= 0) or (self.leg == "short" and w >= 0):
                raise ContractError("pair leg and weight disagree")
        elif self.pair_id is not None or self.leg is not None or w < 0:
            raise ContractError("long/cash signal cannot request short or pair")


def validate_signal_against_run(s: Signal, r: ResearchRun) -> None:
    if s.run_id != r.run_id or s.spec_id != r.spec_id:
        raise ContractError("signal/run lineage mismatch")
    if r.input_coverage_status != "READY":
        raise ContractError("unverified coverage cannot produce usable signals")
