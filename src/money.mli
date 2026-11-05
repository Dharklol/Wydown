(** Exact USD amounts at one microdollar per integer unit.
    Private constructors block accidental conversion from float. *)

type t
type error = Invalid_decimal | Out_of_range

val of_string : string -> (t, error) result
val of_micro : int64 -> t
val to_micro : t -> int64
val to_string : t -> string
val add : t -> t -> (t, error) result
val sub : t -> t -> (t, error) result
(** Multiply a per-share price in microdollars by nonnegative microshares.
    Compute in Zarith and round half-to-even once to a microdollar. *)
val multiply_microshares : price:t -> shares_micro:int64 -> (t, error) result
