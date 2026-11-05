# SPEC-002B — Event envelope, journal and replay contract (proposed v1)

**Status:** REVIEW DRAFT. Parent: #2, #1. The accompanying JSON Schema and
golden scenarios are design fixtures, **not** a production decoder.

## Canonical event envelope
Each event contains:
- `schema_version` (integer, 1), globally unique `event_id` (opaque),
  `event_type`, `environment`, `account_id`, optional `strategy_id`.
- `source_system`, source-scoped `source_event_id`, `producer_version`;
  optional `source_sequence` for broker/feed ordering and `causation_id`.
- `correlation_id` linking business actions; optional `config_digest` and
  `model_digest` for provenance. Digests use explicit algorithms.
- `event_time`: when the upstream economic fact occurred (UTC).
- `observed_at`: when the producer first observed it (UTC).
- `ingested_at`: when the canonical event was durably accepted (UTC).
  The durable journal additionally assigns monotonic `ingest_sequence`.
- `payload`: immutable, event-specific exact-value contract.

UTC timestamp wire format: RFC 3339 Z suffix with optional fractional seconds;
nanosecond maximum precision. Durations and trading-calendar dates have their
own types. A timestamp's printed precision never determines event order.

## Initial broker/market event vocabulary
- `order.accepted`: external or synthetic working limit order acknowledged,
  with order ID, instrument, side, quantity, limit and optional replacement ID.
- `order.canceled`: external confirmed cancellation, not merely a cancel request.
- `execution.fill`: immutable fill ID, order ID, instrument, side, exact
  quantity, price, fee, currency. Cash/inventory arise from this event,
  **not** from duplicated independent cash-posting imports.
- `execution.bust`: explicit reversal of a prior fill; reference target
  execution ID, preserve original and correction evidence.
- `market.mark`: valuation observation with instrument, exact price and
  provenance; never treated as a fill.
- `option.expired`: broker-confirmed worthless expiration event with the
  expired contract quantity. ITM exercise/cash-settlement requires a separate
  event type and explicit broker verification; not silently assumed.

Later contracts should add intents, rejects, replace requests, partial
order state, exercise/assignment, cash settlement, distributions, splits,
corporate actions, margin/collateral balances and FX facts. A required
unknown event must halt a dependent projection instead of being ignored.

## Identity and idempotency
- `(environment, account_id, source_system, source_event_id)` must be unique
  among authoritative facts. `event_id` must also be globally unique.
- Re-delivery of exactly the same canonical event is a no-op (counted as a
  duplicate). Reusing either identity with conflicting bytes/payload is an
  integrity fault and cannot be silently resolved.
- If a provider *revises* a fact, use a distinct correction/bust event linking
  to the original, not an update/delete of history.
- An unacknowledged/unknown broker order must be reconciled before retrying.
  A retry may repeat the *same* idempotent intent; it must not generate a new
  executable order without knowing the previous state.

## Replay and point-in-time policy
- Journal order is durable `ingest_sequence`; *economic* effects are
  projected using the documented ordering appropriate to their type.
  Broker fills use broker sequence where available, else explicit deterministic
  ties and an ambiguity flag if sequence matters for lot accounting.
- A late quote is retained but does not replace a fresher quote just because
  it arrived later. A valuation at `T` selects eligible marks with
  `event_time <= T` **and** known-by `ingested_at <= cutoff`, following
  the source-quality priority and tie policy.
- Previously recorded risk decisions must retain their original as-known
  inputs. Subsequent historical restatement is a separate versioned result,
  never a retroactive change to an already approved order.
- Every projection is reproducible from immutable inputs + schema version +
  projection code version + instrument registry version + configuration hash.
- Distinguish execution-time transaction fees, settled cash and unsettled
  buying power. Do not infer settled buying power from total cash.

## Proposed normalized SQLite tables (illustrative, not committed DDL)
`event_journal`, `source_offsets`, `instrument_versions`,
`accounts`, `order_views`, `fill_views`, `cash_postings`,
`position_lots`, `valuation_marks`, `nav_snapshots`,
`risk_decisions`, `schema_migrations`.
Authoritative events are append-only; projections are replaceable. A fill
and its cash/position postings commit atomically. Use unique keys, foreign
keys, checks, and transaction-scoped idempotency. A schema migration must
have a tested database backup, restoration and rollback/recovery strategy.

## Schema evolution
- `schema_version=1` is the baseline envelope + initial payload vocabulary.
- Unknown major versions and unknown required enum values are rejected.
- Additive optional fields require documented defaults that do not change
  economic meaning. Semantic changes require a new version and fixtures.
- Producer exports maintain source schema and adapter version separately
  from the canonical Wydown schema version.
- No live broker integration is part of v0.2.

## Design test expectations
Golden cases cover a fee-bearing equity fill, duplicate/partial fills,
a fully paid long put expiring worthless, cancel/replace without a fill,
broker fill bust/correction, and a late stale mark. Additional *separate*
fixtures still required before Stage 2 exit: split/dividend, adjusted
option deliverable, partial option exercise/assignment, margin/borrow
liabilities, no-mark/unpriced NAV, and out-of-order ambiguous fills.

One known limitation: JSON Schema describes the wire shape; Python↔OCaml
equivalence, lifecycle transitions, risk authorization and ledger accounting
will be separately verified during Stage 2/3.
