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
- A signed USD money value is represented as checked `int64` in
  `USD_Micro` units (one microdollar = $0.000001). Wire values use decimal
  strings with at most six fractional digits. Reject non-finite values,
  exponents, over-precision, overflow, negative fee expenses and implicit FX.
  Stored money must fit the 64-bit signed range; check *before* conversion.
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
  All multiplication and scaling uses arbitrary-precision integer
  intermediates (`Zarith Z.t` candidate). Never multiply scaled `int64`
  money and quantity directly; preserve the exact intermediate and round
  *once*, at an explicitly identified ledger-posting boundary.
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
  No mark at all => **unpriced**, not zero NAV. Cash and equity liabilities
  have a separate representation from performance metrics. Accounting NAV
  and executable liquidation NAV must remain distinguishable.
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

## Proposed precision, typing and rounding policy
- `Money<USD>` (checked signed microdollars) is distinct from
  `Price<Instrument, USD>`, `Shares<Instrument>`, and
  `Contracts<Instrument>`. OCaml constructors are private: validate ticks,
  units, currency, multiplier, and quantity steps at the boundary. A strategy
  cannot create a validated broker order directly.
- Equity share quantities: integer microshares; option contract quantities:
  whole-number integers. Option premium price is per underlying share,
  multiplied by the point-in-time contract premium multiplier.
- Source numeric strings, option strikes, and quoted prices must first pass
  syntax, precision and tick-size validation. Money and quantities are never
  deserialized through a binary float.
- Use arbitrary-precision integer products for quantity × price × multiplier,
  then **round half to even**, once, to the micro-USD posting scale. Currency
  settlement/conversion follows the provider's stated rule and recorded
  authoritative broker cash amount; different brokerage cent-rounding is a
  reconciled explicit adjustment, never silently discarded or relabeled P&L.
- Record rounding residual/difference and its source rather than implicitly
  hiding it inside a position. The chosen rule is a Wydown accounting-policy
  default, not a claim about every broker's settlement methodology.
- Mathematical indicators, risk forecasts and research statistics may use
  floats, but must cross into order/accounting types through a checked
  conversion that records the value, source and conversion policy.

## Double-entry financial postings
Each authoritative broker execution, fee, cash flow, settlement or confirmed
corporate action produces balanced postings in one SQLite transaction. All
posting accounts use one currency and the micro-USD base unit; the signed
journal sum for each transaction and currency is **exactly zero**. Positions
and lots are associated non-currency quantities, not fake dollar postings.
Typical account roles are cash, security-cost asset, receivables/payables,
external contributed capital, realized trading P&L, fees, dividends,
and rounding/reconciliation differences. Rebuildable views are not a second
source of truth.

- Initial $5,000 funding: debit cash $5,000, credit external capital $5,000.
  **No out-of-band starting cash is authorized** for the pilot.
- Long put premium $250 and fee $1: debit security-cost asset $250,
  debit fee expense $1, credit cash $251. Account NAV marked at the
  initial $250 option value is $4,999. Cost-basis capitalization of fees
  for tax reporting is separate from this economic P&L presentation;
  never count the same fee in both.
- Confirmed worthless expiry: debit realized trading loss $250 and credit
  security-cost asset $250. Remaining cash/NAV is $4,749.
- External contributions and withdrawals are **not returns**. Borrowing, cash
  transfers, margin collateral, tax-lot basis and realized P&L recognition
  require independent postings, even when a broker reports a single net cash
  number. The account does not infer settled purchasing power from NAV.
- A sell must relieve its cost basis, recognize realized P&L and fees exactly
  once, and preserve the selected lot-identification policy. The default
  **research economic** lot convention is FIFO with fee expenses separate;
  broker/tax reporting may have different specific-lot requirements and
  must be reconciled before live capital.

## UNAV — unitized net asset value
The investment performance series is based on **unitized NAV (UNAV)**, not
raw dollar account NAV, so deposits and withdrawals do not look like gains.
- At the first authorized funding event: opening unit price = $1.00,
  issue 5,000 units for $5,000 of capital.
- At a subsequent external flow, price the unit issuance/redemption at a
  recorded **pre-flow** unit price from a valid marked checkpoint. For a
  deposit `D`: `units_added = D / pre_flow_unit_price`.
  Withdrawals burn units by the analogous formula. If pre-flow marks are
  missing/stale or there is inadequate capital/units, halt unitization
  rather than inventing a price.
- UNAV unit inventory uses signed integer **nanounits** (10^-9 units) with
  checked bounds; calculation uses exact rational/big-int intermediates,
  round half to even once at unit mint/burn, and record the rounding
  adjustment separately. Unit-price computation is exact rational until
  published reporting (12-decimal display precision).
- `UNAV_t = marked_account_NAV_t / units_outstanding_t`.
  `unit_return_t = UNAV_t / UNAV_{t-1} - 1` between external flows.
  `drawdown_t = 1 - UNAV_t / max(UNAV_s for s <= t)` on comparable
  post-flow unit prices. The 30% threshold remains a planning guide only.
- UNAV is *not* a legal mutual-fund NAV; it is an internal performance
  measure. If liabilities, external flows, unknown marks, or unit supply
  are inconsistent, report unpriced/invalid rather than a number.

## Still to ratify before production implementation
1. USD micro precision, microshares and nanounits are **proposed accepted
   defaults**; prove signed bounds, rounding and overflow in OCaml tests.
   Multi-currency support and large account sizing remain out of v0.2.
2. Time-in-force, broker settlement and clearing-account conventions.
3. Point-in-time instrument registry updates and detailed adjusted-option
   handling (tracked for later implementation).
4. Confirm broker/tax-lot and fee-capitalization policy before live capital;
   FIFO is the research ledger default.
5. Initial account/broker capability matrix, ITM option expiration, exercise
   and assignment controls (tracked for later implementation).
