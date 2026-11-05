open Wydown_core

let get_money s =
  match Money.of_string s with
  | Ok v -> v
  | Error _ -> failwith ("Unexpected invalid money: " ^ s)

let check expected actual =
  if expected <> actual then
    failwith (Printf.sprintf "expected %s, received %s" expected actual)

let () =
  check "123.456789" (Money.to_string (get_money "123.456789"));
  check "-0.000001" (Money.to_string (get_money "-0.000001"));
  check "0.000000" (Money.to_string (get_money "0"));
  assert (Money.of_string "1e3" = Error Money.Invalid_decimal);
  assert (Money.of_string "0.1234567" = Error Money.Invalid_decimal);
  assert (Money.of_string "01.00" = Error Money.Invalid_decimal);
  assert (Money.of_string "-0" = Error Money.Invalid_decimal);
  assert (Money.of_string "9223372036854.775808" = Error Money.Out_of_range);
  let hundred = get_money "100.000000" in
  let twenty = get_money "20.000000" in
  (match Money.add hundred twenty with
   | Ok x -> check "120.000000" (Money.to_string x)
   | Error _ -> failwith "add failed");
  assert (Money.add (Money.of_micro Int64.max_int) twenty = Error Money.Out_of_range);
  let micro = 1L in
  (match Money.multiply_microshares
      ~price:(get_money "123.456789") ~shares_micro:micro with
   | Ok x -> check "0.000123" (Money.to_string x)
   | Error _ -> failwith "microshares multiply failed");
  (match Money.multiply_microshares
      ~price:(get_money "0.500000") ~shares_micro:micro with
   | Ok x -> check "0.000000" (Money.to_string x)
   | Error _ -> failwith "half-even failed");
  (match Money.multiply_microshares
      ~price:(get_money "1.500000") ~shares_micro:micro with
   | Ok x -> check "0.000002" (Money.to_string x)
   | Error _ -> failwith "half-even odd failed");
  assert (Money.multiply_microshares ~price:hundred ~shares_micro:(-1L)
          = Error Money.Invalid_decimal);
  (match Quantity.shares_from_micro ~step_micro:1L 1L with
   | Ok q -> assert (Quantity.microshares q = 1L)
   | Error _ -> failwith "valid microshares rejected");
  assert (Quantity.shares_from_micro ~step_micro:1_000_000L 1L
          = Error Quantity.Invalid_lot_step);
  assert (Quantity.contracts_from_int 0L = Error Quantity.Invalid_quantity);
  (match Quantity.contracts_from_int 2L with
   | Ok n -> assert (Quantity.contract_count n = 2L)
   | Error _ -> failwith "valid contracts rejected")
