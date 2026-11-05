(** Distinct share and option-contract quantities, both whole scaled integers. *)
type shares
type contracts
type error = Invalid_quantity | Invalid_lot_step

val shares_from_micro : step_micro:int64 -> int64 -> (shares, error) result
val contracts_from_int : int64 -> (contracts, error) result
val microshares : shares -> int64
val contract_count : contracts -> int64
