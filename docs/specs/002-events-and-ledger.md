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
- `ingested_at`: when a canonical *economic* event was first durably
  accepted (UTC). Delivery attempts/redeliveries have separate receipt
  timestamps and metadata. The durable journal assigns a monotonic
  `ingest_sequence` to each accepted economic fact.
- `payload`: immutable, event-specific exact-value contract.

UTC timestamp wire format: RFC 3339 Z suffix with optional fractional seconds;
nanosecond maximum precision. Durations and trading-calendar dates have their
own types. A timestamp's printed precision never determines event order.

## Initial broker/market event vocabulary
- `order.accepted`: external or synthetic working limit order acknowledged,
  with order ID, instrument, side, quantity, limit and optional replacement ID.
- `order.canceled`: external confirmed cancellation, not merely a cancel request.
- `execution.fill`: immutable broker-scoped fill ID, order ID,
  instrument, side, exact quantity, price, fee, currency. Cash and inventory
  derive from this authoritative fill **once**, not from duplicated
  independent cash-posting imports.
- `cash.flow`: authoritative external deposit or withdrawal, unique flow
  ID, positive exact amount, currency, and external-funding classification.
  The initial $5,000 deposit is a journal event, not a test harness balance.
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
- `(environment, account_id, source_system, source_event_id)` must be
  unique for authoritative economic facts; `event_id` is also unique for
  accepted canonical facts. Broker order/execution IDs are additionally
  scoped by broker connection and account.
- A receipt attempt is **not** a new economic fact. Separate the immutable
  accepted event from an append-only record of delivery attempts
  (`received_at`, raw bytes/hash, transport diagnostics).
- De-duplicate using the scoped stable source identity **and an exact
  normalized economic fact fingerprint** covering type, account, source
  event time/sequence, currency, quantities, prices, fees and event payload.
  Canonical `event_id`, `observed_at`, `ingested_at`, producer version,
  correlation IDs and other transport metadata do not change the fingerprint
  by themselves. A duplicate with later receipt timestamps is a no-op in
  economic state, though its receipt remains auditable.
- Reuse of a stable source identity with *different* normalized economic
  content is an integrity fault, not an ordinary duplicate. A provider
  correction receives a **new source ID and linked correction/bust event**.
  If the upstream provider offers no stable ID, the adapter must define,
  document and test its source-specific identity policy; it cannot silently
  assume two similar-looking trades are identical.
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
  it arrived later. A valuation at economic time `T` and knowledge cutoff
  `K` uses eligible marks satisfying **both** `event_time <= T` and
  `ingested_at <= K`. Quote selection applies source-quality/age,
  session and tie rules; missing eligible marks result in UNPRICED state,
  not zero NAV. A future-dated event cannot be assumed known historically.
- Similarly, cash, fills, corrections, and option lifecycle events are
  included only if known by cutoff `K`, with their economic effective time
  and broker ordering treated explicitly. An as-known report is immutable;
  a newly discovered historical event produces a separately versioned
  restatement and never retroactively changes an executed risk decision.
- Previously recorded risk decisions must retain their original as-known
  inputs. Subsequent historical restatement is a separate versioned result,
  never a retroactive change to an already approved order.
- Every projection is reproducible from immutable inputs + schema version +
  projection code version + instrument registry version + configuration hash.
- Distinguish execution-time transaction fees, settled cash and unsettled
  buying power. Do not infer settled buying power from total cash.
- Every accepted financial event projects a **balanced double-entry** cash/
  investment/capital/income/expense posting transaction. The currency-denominated
  postings sum exactly to zero, including fees and rounding adjustments.
  The immutable event and derived postings commit atomically. External flows
  mint/burn UNAV units at a recorded pre-flow price: raw NAV changes, but
  the performance unit price does not solely because of a contribution.
- Rebuild checkpoints contain projector version, exact registry version,
  accepted-event range, time `T`, knowledge cutoff `K` and policy hash.
  An account projection cannot be called reconciled merely because its
  arithmetic balances: independently compare broker cash, working orders,
  inventory and corporate actions.

## Proposed normalized SQLite tables (illustrative, not committed DDL)
`event_journal`, `receipt_attempts`, `source_offsets`,
`instrument_versions`, `accounts`, `order_views`, `fill_views`,
`posting_transactions`, `ledger_postings`, `position_lots`,
`valuation_marks`, `nav_snapshots`, `unav_units`,
`risk_decisions`, `schema_migrations`.
Use SQLite **STRICT** tables, foreign keys, unique keys, CHECK constraints,
integer-scaled financial columns, and transaction-scoped idempotency.
An accepted fact, the derived balanced postings and projection checkpoint
must commit atomically or not at all. Append-only source events and
audit-worthy receipt attempts are authoritative; projections are rebuildable.
Account registry/instrument versions are effective dated. A schema
migration requires tested backup, restoration and recovery policy; do not
assume downgrading an old binary automatically reverses financial schema.

## Schema evolution
- `schema_version=1` is the baseline envelope + initial payload vocabulary.
- Unknown major versions and unknown required enum values are rejected.
- Additive optional fields require documented defaults that do not change
  economic meaning. Semantic changes require a new version and fixtures.
- Producer exports maintain source schema and adapter version separately
  from the canonical Wydown schema version.
- No live broker integration is part of v0.2.

## Design test expectations
Golden cases cover **journal-funded opening capital**, a fee-bearing
equity fill, source-identity duplicate with changed receipt metadata,
partial fills, a fully paid long put expiring worthless, cancel/replace
without a fill, broker fill bust/correction, and a late stale mark.
Further tests should exercise unitized NAV with an external mid-run
contribution, equity sell/realized P&L and 12-decimal intermediate products.
Additional *separate* fixtures still required before Stage 2 exit:
split/dividend, adjusted option deliverable, partial option exercise/
assignment, margin/borrow liabilities, no-mark/unpriced NAV, out-of-order
ambiguous fills, negative/boundary input and actual JSON Schema conformance.
The latter three families are also tracked as deferred implementation
findings; they are not waived from Stage 2 acceptance.

One known limitation: JSON Schema describes the wire shape; Python↔OCaml
equivalence, lifecycle transitions, risk authorization and ledger accounting
will be separately verified during Stage 2/3.
