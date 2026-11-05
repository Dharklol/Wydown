type t = int64
type error = Invalid_decimal | Out_of_range

let scale = Z.of_int 1_000_000
let max_value = Z.of_int64 Int64.max_int
let min_value = Z.of_int64 Int64.min_int

let checked z =
  if Z.gt z max_value || Z.lt z min_value then Error Out_of_range
  else Ok (Z.to_int64 z)

let digits s =
  String.length s > 0 &&
  String.for_all (fun c -> c >= '0' && c <= '9') s

let of_string input =
  let len = String.length input in
  if len = 0 then Error Invalid_decimal
  else
    let negative = input.[0] = '-' in
    let raw = if negative then String.sub input 1 (len - 1) else input in
    let parts = String.split_on_char '.' raw in
    let parsed =
      match parts with
      | [whole] -> Some (whole, "")
      | [whole; fraction] when fraction <> "" -> Some (whole, fraction)
      | _ -> None
    in
    match parsed with
    | None -> Error Invalid_decimal
    | Some (whole, frac) ->
      if not (digits whole) ||
         (String.length whole > 1 && whole.[0] = '0') ||
         String.length frac > 6 ||
         (frac <> "" && not (digits frac))
      then Error Invalid_decimal
      else
        let whole_z = Z.of_string whole in
        let fraction_z =
          if frac = "" then Z.zero
          else Z.mul (Z.of_string frac)
            (Z.pow (Z.of_int 10) (6 - String.length frac))
        in
        let z = Z.add (Z.mul whole_z scale) fraction_z in
        let signed = if negative then Z.neg z else z in
        if negative && Z.equal z Z.zero then Error Invalid_decimal
        else checked signed

let of_micro x = x
let to_micro x = x

let to_string x =
  let value = Z.abs (Z.of_int64 x) in
  let whole = Z.div value scale in
  let frac = Z.to_int (Z.rem value scale) in
  let sign = if Int64.compare x 0L < 0 then "-" else "" in
  Printf.sprintf "%s%s.%06d" sign (Z.to_string whole) frac

let add x y = checked (Z.add (Z.of_int64 x) (Z.of_int64 y))
let sub x y = checked (Z.sub (Z.of_int64 x) (Z.of_int64 y))

let divide_half_even numerator denominator =
  let quotient, remainder = Z.ediv_rem (Z.abs numerator) denominator in
  let twice_remainder = Z.mul remainder (Z.of_int 2) in
  let choose_up =
    Z.gt twice_remainder denominator ||
    (Z.equal twice_remainder denominator &&
     Z.equal (Z.rem quotient (Z.of_int 2)) Z.one)
  in
  let rounded = if choose_up then Z.succ quotient else quotient in
  if Z.sign numerator < 0 then Z.neg rounded else rounded

let multiply_microshares ~price ~shares_micro =
  if Int64.compare shares_micro 0L < 0 then Error Invalid_decimal
  else
    checked (divide_half_even
      (Z.mul (Z.of_int64 price) (Z.of_int64 shares_micro)) scale)
