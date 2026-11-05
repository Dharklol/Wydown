type shares = int64
type contracts = int64
type error = Invalid_quantity | Invalid_lot_step

let shares_from_micro ~step_micro n =
  if Int64.compare step_micro 0L <= 0 then Error Invalid_lot_step
  else if Int64.compare n 0L <= 0 then Error Invalid_quantity
  else if Int64.rem n step_micro <> 0L then Error Invalid_lot_step
  else Ok n

let contracts_from_int n =
  if Int64.compare n 0L <= 0 then Error Invalid_quantity else Ok n

let microshares x = x
let contract_count x = x
