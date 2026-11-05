# Wydown v0.2: research-safe, deterministic portfolio kernel

**State:** design roadmap; not a live-trading authorization.
**Mandate:** isolated $5,000 pilot, 30% drawdown **planning** threshold.
**Independent sleeves:** global equity index, value+quality, cross-asset trend,
cross-sectional momentum, pairs/statistical arbitrage, data-center credit.

## Non-negotiable engineering policy
- Runtime core in OCaml; strategy research in Python.
- SQLite operational storage; TOML human-readable settings; JSON only where wire/API contracts require it.
- No broker credentials or direct broker APIs in research and paper runtimes.
- Keep paper, research and live P&L separate; require explicit model promotion.
- Short stock and derivatives are represented by instruments, not by an overly broad 'long-only' data model.
- Margin loans disabled. Fully paid long options only after approvals and tests; naked short options prohibited.
- All portfolio accounting uses checked exact units and currency precision; no binary floats in ledger arithmetic.
- The production release and approved risk policy are immutable and independently identifiable.
- Existing data-center burn-in remains frozen; integrate through a separately versioned adapter.

## Stage 1 — Data contract, RFC sign-off (Issues #1, #2)
Deliver: typed instrument registry (including options), exact money/tick/quantity
representation, UTC timestamps, immutable event envelope, source provenance,
schema evolution rules, complete order/fill/cash/position/valuation dictionary.
Provide golden fixtures for share buy/sell, put purchase, option expiry,
duplicate/partial fill, cancel/replace, broker correction and late market data.

**Gate:** a reviewer can reconstruct all expected effects from fixture data,
with unambiguous Python/OCaml/SQLite mapping. No production implementation yet.

## Stage 2 — Accounting and risk vertical slice (Issues #2, #3)
Deliver: OCaml validator, SQLite event journal + deterministic rebuildable
projections, reconciliation, NAV/drawdown/cash/equity- and option-risk reports.
Add explicit risk permission matrix and fail-closed synthetic order screening.
Simulate crash/restart, partial fills, duplicate messages, stale quotes,
corporate-action events and expiration lifecycle.

**Gate:** replay identical state and risk decisions after restart, including
negative tests; no account credentials, real-order network route, or reliance
on live data.

## Stage 3 — Reproducibility, release discipline, adapter (Issues #4, #5)
Deliver: tested dependency locks, fixed compiler/build image, immutable release
manifest, versioned SQLite migrations and restore drill, Python-to-OCaml
canonical adapter and golden parity replay from frozen data-center output.

**Gate:** reproduce the same validated artifact/equivalent documented build
on a clean runner; replay fixtures and confirm schema upgrade/rollback
recovery; no unreviewed changes to the existing data-center burn-in.

## CI rollout (start immediately, increase as capabilities exist)
0. Bootstrap: syntax/whitespace, prohibited files and keys, immutable external
   GitHub Action references, quality-gate self-tests. **Not** an OCaml test.
1. Once project source exists: pinned OCaml/opam/Dune, formatting, warnings-as-errors,
   dependency resolution and unit/property tests.
2. Once DB/risk code exists: schema migrations, accounting replay, negative-risk
   fixtures, restart/idempotency, option exercise/expiration, and backup restore.
3. Once adapters exist: Python-OCaml golden parity, timestamp/contract validation,
   OOS lineage, conservative risk checks. No live deploy from PR merge.
4. Production eligibility later: paper → manually approved micro-live; release
   manifest, policy hash, broker permissions and independent health monitors.

**Important:** CI *runs* tests; only a correctly configured repository branch
ruleset/protection can make checks mandatory and block direct merges/pushes.
For a private personal repo, verify that the GitHub plan supports protections.

## Strategy research after v0.2
Parallel research lanes, sequential promotion:
1. Cross-asset trend: liquid diversified proxies, parameter stability, crises.
2. Value+quality: cross-sectional factor definitions, universe/survivorship,
   sector neutrality and rebalance costs.
3. Cross-sectional momentum: anti-lookahead/point-in-time universe, turnover,
   crash exposure, factor overlap with value+quality.
4. Pairs/stat arb: cointegration/relationship breakdown, borrow/short fees,
   fill/slippage, broker feasibility at $5,000.
5. Data-center credit: continue existing frozen burn-in and adapter parity;
   options implementation requires distinct backtest, not substitution.
6. Global equity indexing: passive benchmark and live-eligible core,
   subject to portfolio risk gates.

Acceptance for every strategy: immutable training/test periods, forward paper
ledger, executable bid/ask/cost simulation, after-cost and portfolio-incremental
performance, sensitivity/stress/conditional dependence, documented invalidation,
separate manually approved micro-live gate. Research lanes can share data and
tooling but must not share fitted parameters or leak future information.

## Proposed v0.2 release boundary
A validated **paper-only** portfolio accounting/risk kernel with reproducible
builds. No broker routing or live capital control.
