# Research interface handoff (draft, no execution authority)

The externally frozen **5 November 2026 research spec v1.0** is a separate
research contract. Do not duplicate proprietary strategy rules, performance
results, or dataset contents in this public repository.

The merged Wydown canonical events describe **financial facts** (cash, marks,
orders, fills, corrections). The research-only Python `ResearchRun` and
`Signal` describe provenance and intended exposure. They must never be
presented as broker fills, risk-approved orders, or validated returns.

Fields: immutable run ID, frozen spec/version, code/config/source snapshot
hashes, chronological split, seed, data readiness, run timestamp;
signal instrument ID, point-in-time `as_of_utc`, `available_at_utc`,
`earliest_trade_at_utc`, exact score/target weight, explanation, source
snapshot IDs; pairs additionally have pair ID and explicit long/short leg.

This lightweight gate enforces time ordering and prevents live authorization,
but **does not** verify historical vendor availability, actual session
calendars, point-in-time fundamentals, market data or execution feasibility.
The baseline requires next regular-session open and delay scenarios; those
are upcoming session-calendar/execution-layer invariants, not assumptions
that every later UTC timestamp is a valid fill.

## Readiness audit (no research data source yet verified)

| Family | Required sources | Status |
| --- | --- | --- |
| TREND-01 | ETF identity/adjustments, historical return series, raw opens, cash rates, sessions | UNVERIFIED |
| VQ-01 | Original-published fundamental vintages, historical identities, delistings, splits/dividends, raw prices | DATA-BLOCKED pending original-vintage vendor proof |
| MOM-01 | Historical complete equity universe, total returns, liquidity, delisted proceeds, sessions | UNVERIFIED |
| PAIR-01 | Equity data plus historical borrow/recall/collateral/short-distribution evidence | DATA-BLOCKED for live feasibility; backtest feasibility unverified |

A missing verified source is a **data-readiness blocker**, not an alpha
rejection. Keep missing values distinct from zero. Never use today's
constituents or revised filings as historical vintage, or create synthetic
performance claims. Do not open the reserved performance block to fix
missingness or select strategy parameters.

## Interface before strategy backtests

1. Inventory actual available data and record source licenses, mappings,
   point-in-time publication/availability and historical coverage by year.
2. Build effective-dated security/issuer master and raw vs total-return
   observations separately, including corporate action and delisting cash.
3. Implement actual exchange sessions and settlement policies; no
   signal-close fill, no execution before known data and next session.
4. Record immutable run manifests and simulation costs. A candidate's
   hypothetical fill must remain separate from a real broker economic fact.
5. Independently reconcile research ledger with the future OCaml accounting
   kernel before any portfolio-level promotion.

## Existing data-center model

It remains in frozen credit-plumbing burn-in and is not modified here.
The Pi controller available through this conversation is limited to
the Kalshi recorder project, not the separate credit-plumbing workspace.
An authorized future integration should be **read-only exports** of frozen
snapshot and paper-output events, each with effective/known timestamps,
source hash, model version and provenance. No backfilled 'live' evidence,
and no data-center P&L correlation until synchronized real measures exist.
