# Wydown Engineering Standards — financial correctness policy

**Status:** Stage-1 proposed convention; reviewed by PR. Not automatically
enforced by GitHub rulesets. Linked specifications: #1, #2; implementation
hardening tracker: #10.

## Scope and operating boundaries
- OCaml is the production language for canonical types, accounting, portfolio
  and risk decisions, and (in a later release) the authorized OMS gateway.
  Python is permitted for experimental research, fixtures and independent
  reference oracles. Cross-language parity is a release gate.
- SQLite is the local authoritative operational data store. Prefer
  **`STRICT` tables**, integer-scaled monetary and quantity columns,
  foreign keys and checked constraints. TOML is human-maintained config;
  wire/API contracts use their required formats (JSON for current events).
- Research/paper/live identity and credentials are segregated, checked on
  every boundary; v0.2 ships **paper-only**, without any broker order route.
- No model, credential, original account data, strategy parameters or
  research output considered proprietary belongs in the public repository.
  Making the repository private later cannot erase prior public history.

## Arithmetic, currency, quantities
- Wire money/price/quantity values: exact decimal strings, no JSON numeric
  floats, no exponent notation, six fractional decimal places maximum
  for the initial USD and share conventions.
- OCaml private constructors for `Money<USD>`, per-instrument price,
  microshares (10^-6 share), option whole contracts, and UNAV nanounits
  (10^-9 portfolio units). Currency and instrument metadata must be checked
  before arithmetic.
- Stored USD money: signed checked int64 microdollars (10^-6 USD). Use
  arbitrary-precision signed integers (e.g., Zarith `Z.t`) for intermediate
  products of scaled price × quantity × multiplier; check bounds on
  quantization and before persistence.
- Quantize to micro-USD **once per defined posting amount**, round-half-even;
  allocations of lot cost must conserve the original microdollar basis
  exactly, distributing the residual to the final partial disposal.
- Rounding must never silently change broker-reported cash. Broker settlement
  amounts are reconciled to computed posting amounts; differences have
  explicit provenance and a posting entry, not hidden P&L.
- Research/risk models may calculate floats, but source, timestamp,
  rounding/conversion policy and risk validation are required when crossing
  into financial accounting/decisions. Statistical forecast values are not
  spendable money or precise contract quantities.

## Typed instruments and event lifecycle
- Stable internal instrument IDs with effective-dated metadata. Names/tickers
  are aliases; never assume an option contract always means 100 shares.
- Premium quote multiplier, exercise settlement and deliverable are distinct.
  Trade side/position direction are distinct from margin permission.
- Strategy **signal** → proposed **intent** → risk verdict → broker
  acknowledgment/execution → immutable journaled financial fact.
  Rejection, cancellation request, cancellation confirmation, execution,
  correction and settlement are separate states.
- Unrecognized required event, unknown instrument type or metadata, missing
  mark, stale data, uncertain working order, or unsupported exercise/assignment
  must produce explicit fail-closed state, not implicit zero/filled/canceled.
- Accepted economic facts are immutable. Receipt attempts are tracked
  independently of facts; duplicate deliveries cannot double-post cash.
  Semantic corrections/busts reference the original fact and carry new IDs.

## Ledger and portfolio performance
- All accepted cash and trade facts derive **balanced double-entry** postings
  in one atomic transaction per economic event. Check sum(debits - credits)
  == 0 at exact micro-USD precision for every currency.
- Distinguish position quantities, acquisition cost, commissions, realized
  trading P&L, unrealized P&L, distributions, external flows, settled cash,
  unsettled cash and available buying power.
- Initial $5,000 is a real funding event in the synthetic pilot ledger.
  Default research economic lot matching is **FIFO**; tax/broker-specific
  basis rules require explicit reconciliation before live deployment.
- Use **unitized net asset value (UNAV)** for flow-adjusted portfolio
  returns/drawdowns. Initial $5,000 deposit issues 5,000 units at $1.
  Contributions/withdrawals mint/burn units at a valid recorded pre-flow
  unit price, and do not count as returns.
- NAV marks require economic valuation time *and* as-known cutoff. Preserve
  source/ingest ordering, restatement version and provenance; no future data.
  Accounting mid and executable liquidation marks must be identified
  separately, not conflated for simulated strategy performance.

## Storage, deployment and governance
- SQLite durable event journal and receipt audit records are append-only.
  Derived cash, positions, lots, UNAV, marks and risk views are rebuildable
  and versioned. Transactionality, unique broker/source IDs, crash/restart
  and reprocessing idempotency are required.
- Use local single-writer SQLite; WAL, foreign-key checks, synchronous
  FULL and consistent online backup/restore drills in deployed configuration.
- Do not ship schema migrations without fixtures and recovery tests. Downgrade
  requires an explicit tested plan, not silent schema mutation.
- Dune/opam compiler, direct/transitive packages, build environment, C libs,
  SQLite version, sources, artifact and approved risk policy are pinned or
  fingerprinted. No dependency auto-update or automatic live deployment.
- CI initially checks hygiene and synthetic reference fixtures. Add real
  OCaml unit/property/replay/migration/negative-risk checks as implementation
  lands. A green CI check is evidence of tested properties, **not** a
  mathematical guarantee of accounting or strategy correctness.
- Public GitHub changes through reviewed PRs with required checks. Privileged
  operational approvals and live capital promotion require independent
  controls beyond merge permissions.

## Deferred, not forgotten
See #10 for the nanosecond-safe parser, adjusted option exercise/assignment,
and complete schema validation/negative-path coverage. Implement before
their respective production boundary becomes active.
