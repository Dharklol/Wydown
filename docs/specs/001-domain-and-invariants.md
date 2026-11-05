# SPEC-002A — Canonical domain and arithmetic contract (proposed v1)

**Status:** REVIEW DRAFT. Parent: #2, #1. Scope: schema/fixtures only; no executable trading permission.

## System boundary
A strategy emits a **signal**; a portfolio planner derives an **intent**; the
risk gateway independently approves or denies it; a broker then reports an
**order state** and possibly **fills**. None is interchangeable. The paper
executor can emit synthetic broker facts, but live broker facts must remain
distinguishable by deployment/environment and account identity.

## Enumerated domains
- `environment`: `research`, `paper`, `live`. No implicit conversion.
- `account_id`: stable opaque identifier. An account never silently combines
  real holdings outside Wydown's independent pilot.
- `instrument`: tagged union of `cash`, `equity` (including ETFs), `option`;
  future instruments require explicit schema revision.
- `strategy_id`: independent source identifier, **not** an execution privilege.
- `side`: `buy`, `sell`, `sell_short`, `buy_to_cover`. All four can be
  represented in research; live eligibility is a separate broker/account/risk policy.

## Exact arithmetic
- Human/wire quantities, prices, fees, strikes, and marks are **decimal strings**,
  never JSON numeric floating-point values.
- A signed USD money value is parsed into a checked integer count of
  `USD_Micro` (one microdollar = $0.000001). Max 6 decimal places; reject
  non-finite, exponent, over-precision, overflow, negative fees and unintended
  currency conversion. The 64-bit integer range caps representable notional;
  checks must occur *before* arithmetic.
- The initial wire format carries `currency: "USD"`. The domain type carries
  its currency, even though multi-currency settlement is **not** in v0.2.
- An equity quantity may have up to 6 decimal places, subject to the registry's
  lot/increment. An option quantity is a whole number of contracts.
- `price` is quoted **per share** for equities and **per underlying share**
  for standard US equity options. `premium_multiplier` converts the latter
  to per-contract cash amount; it is registry data and is not parsed from a
  symbol. Adjusted options can have separate deliverables and multipliers.
- For a standard option buy, debit =
  `quantity_contracts * premium_per_share * premium_multiplier + fee`.
  Exact checked arithmetic and an explicit rounding policy are mandatory.
- Instrument tick size, quantity step, settlement currency, market calendar,
  premium multiplier, strike, right, style, cutoff, expiry and deliverable
  must be available in the registry *at the effective time*.
- No arithmetic on two different currencies or units without an explicit
  conversion event and recorded rate/source.

## Derived account state
- Canonical source events are immutable. Projections of cash, lots, positions,
  fees, settled/unsettled balances, available buying power, and NAV are
  rebuildable and are not competing sources of truth.
- For a fully paid equity buy at price P, quantity Q, and fee F:
  cash change = `-(Q*P + F)`; shares change = `+Q`.
  A sell reverses shares and credits `Q*P - F`.
- For a long option buy, cash decreases by paid premium and fees, while
  option contracts increase. Gross derivative *notional*, premium at risk,
  delta-equivalent exposure, expiry obligations and stressed loss are distinct.
- Current NAV = cash plus marked value of owned positions minus liabilities,
  with valuation timestamps, mark policies and fee recognition recorded.
  No mark at all => **unpriced**, not zero NAV.
- A short position can be represented with signed inventory and associated
  borrow/financing/collateral liabilities in paper research. A live short-stock
  order is **not** authorized while the margin/borrow capability is disabled.
- Fully paid long puts and calls may be eligible *after* independent validation
  and broker permissions. Naked short options are prohibited; collateralized
  short options are deferred.
- Exercise/assignment can create stock obligations even without an explicit
  stock order. v0.2 must fail closed on unsupported in-the-money expiry,
  exercise/corporate-action and broker lifecycle states; a long put is **not**
  permission to create uncovered short shares.

## Validation and risk boundary
- A `signal.generated` record is not a fill, order, or permission.
- Unknown instrument metadata, invalid tick size, stale mark, unsupported
  corporate action, ambiguous buying power or uncertain broker order state
  blocks new execution. Never infer a missing field as zero.
- `30%` is the isolated pilot's drawdown *planning* threshold, not a
  deterministic loss bound. Portfolio risk limits and promotion gates remain
  separate from this transport contract.
- The golden examples are synthetic; none are broker-specific trading advice.

## Still to ratify before production implementation
1. Supported exact-decimal scale, any non-USD currency, and maximum order size.
2. Time-in-force, broker settlement/clearing account conventions.
3. Point-in-time instrument registry updates and option adjustment handling.
4. FIFO/average-cost/tax-lot rules and fee allocation for realized P&L.
5. Initial account/broker capability matrix and option expiration controls.
