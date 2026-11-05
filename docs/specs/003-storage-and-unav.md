# SPEC-002C — SQLite journal, postings and UNAV representation

**Status:** Stage-1 design, not a migration or executable production database.
Parent: #2. No SQLite database is created by this specification.

## Authoritative-versus-derived boundary
1. The upstream immutable economic event is accepted once, under a globally
   unique `event_id` and a source-scoped deduplication key.
2. Raw delivery receipts (including rejected/conflicting deliveries) are
   separately auditable, with transport data and timestamps that never
   change an already accepted broker fact.
3. A validated economic event is journaled and its deterministic **balanced**
   postings/projector updates are committed in one transaction.
4. Position, lot, order, valuation and risk views can be dropped/rebuilt from
   the immutable journal *and* effective-dated account/instrument metadata.
5. Reconciliation against broker-reported balances/working orders/corporate
   actions is a separate explicit gate; balanced postings alone do not
   establish that broker state and our state agree.

## Initial table families
- `accounts`, `instrument_versions`: account registry and effective-dated
  equity/option metadata; no hardcoded option contract multiplier.
- `event_journal`: authoritative facts keyed by event ID and unique
  (environment, account_id, source_system, source_event_id); canonical
  fingerprint excludes arrival-only metadata; journal has monotonic
  ingestion sequence.
- `receipt_attempts`: each intake attempt, source ID, observed/received
  timestamp and source payload digest; duplicates and conflicts are
  retained as audit status, not reposted as economic facts.
- `posting_transactions` and `ledger_postings`: 1-to-many derived,
  exact integer micro-USD postings with unique (transaction, line) IDs.
- `cash_balances`, `position_lots`, `working_orders`: derived views with
  source projector/version metadata and replay checkpoints.
- `valuation_marks`, `nav_snapshots`, `unav_units`: timestamped mark
  provenance, account cash/assets/liabilities and flow-adjusted unit supply.
- `risk_decisions`: immutable policy and as-known portfolio inputs,
  linked to pretrade intents. No production live order gateway in v0.2.
- `schema_migrations`: migration ID, checksum, prior version, completed at,
  validation and backup/restore reference.

## SQL modeling illustration (NOT a migration)
The first implementer can start with the following **illustrative** subset,
without treating it as a complete/approved schema:

```sql
CREATE TABLE event_journal (
    journal_seq INTEGER PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    environment TEXT NOT NULL
      CHECK(environment IN ('research','paper','live')),
    account_id TEXT NOT NULL,
    source_system TEXT NOT NULL,
    source_event_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    economic_hash TEXT NOT NULL,
    event_time_ns INTEGER NOT NULL,
    first_ingested_ns INTEGER NOT NULL,
    canonical_payload_json TEXT NOT NULL,
    UNIQUE(environment, account_id, source_system, source_event_id)
) STRICT;

CREATE TABLE posting_transactions (
    tx_id TEXT PRIMARY KEY,
    origin_event_id TEXT NOT NULL REFERENCES event_journal(event_id),
    currency TEXT NOT NULL CHECK(currency = 'USD'),
    projector_version TEXT NOT NULL
) STRICT;

CREATE TABLE ledger_postings (
    tx_id TEXT NOT NULL REFERENCES posting_transactions(tx_id),
    line_no INTEGER NOT NULL CHECK(line_no >= 0),
    ledger_account TEXT NOT NULL,
    amount_micro INTEGER NOT NULL,
    PRIMARY KEY(tx_id, line_no)
) STRICT;
```

These `STRICT` tables enforce storage classes/uniqueness, **not** a sum
across separate posting rows. The Stage-2 projector must validate
`sum(amount_micro) == 0` using overflow-safe arithmetic before commit,
and tests must verify no partial or unbalanced transaction can be exposed
as accepted. A guarded commit/finalization mechanism or other DB-side
integrity method is desirable before operational deployment.

## Funds and cost basis
- External funding: debit cash +5000, credit contributed capital -5000.
  This creates initial 5,000 UNAV units at $1 each; it is not income.
- Equity or long-option buy: debit investment cost, debit fees, credit cash.
  Separately increase exact share/contract quantity and FIFO lot basis.
- Sell: debit cash net of fees, debit fees, credit relieved cost basis and
  credit realized gain (or debit realized loss); net P&L arises once.
- Confirmed worthless long-option expiry: debit realized loss, credit
  relieved option cost; no synthetic broker sale proceeds.
- Bust: append a linked correction event and balanced reversing postings.
  If a fill affected subsequently consumed lots, correct/replay the
  dependent lot graph, not only the latest quantity.
- Settlement and broker cash reconciliations may add explicit receivable,
  payable and adjustment postings. All fee/broker basis differences are
  documented, not silently incorporated into return.

## UNAV accounting policy
Opening deposit `$5000` => NAV `$5000`, unit supply `5000.000000000`,
UNAV `1.0`. A later deposit after the portfolio rises to a pre-flow
NAV of `$5100` and 5000 units is priced at `$1.02/unit`. A `$1020`
deposit issues exactly `1000` units: cash/NAV rise to `$6120`,
units to `6000`, and UNAV stays `1.02`. If assets subsequently gain
`$60`, NAV is `$6180`, UNAV `1.03`.

Compute both unit changes and unit prices using exact rational or
arbitrary-precision integer intermediates; store integer nanounits, integer
micro-USD NAV, and provenance. Unit price is derived as the ratio of the
two; 12-decimal display formatting does not become the authoritative price.
A fractional-unit mint/burn rounding residual is separately recorded and
must never be disguised as performance. Missing a valid pre-flow mark
makes the unitization checkpoint invalid.

Returns and drawdown use the **unit-price history**, not the raw NAV high
water mark. External cash flows do not count as trading gains, and
opening deposits are not P&L.

## Deferred implementation work
- Exact authoritative versus as-known mark reconciliation, quote source
  priority, nanosecond timestamp parsing and session calendars (#10).
- Detailed option deliverable/expiration/exercise/assignment and broker
  cash settlement models (#10).
- Complete JSON Schema validator, negative source fixtures and backend
  invariant tests (#10).
- Broker-specific settled/unsettled cash buying-power rules, borrow fees
  and collateral when applicable; no margin loan in initial pilot.
