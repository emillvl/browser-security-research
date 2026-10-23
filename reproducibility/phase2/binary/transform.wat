(module
 (func (export "transform") (param $x i32) (param $y i32) (result i32)
  (local $round i32)
  (loop $mix
   local.get $x
   local.get $y
   i32.xor
   i32.const 7
   i32.rotl
   i32.const 1664525
   i32.mul
   i32.const 1013904223
   i32.add
   local.set $x
   local.get $y
   local.get $x
   i32.const 13
   i32.rotr
   i32.xor
   local.set $y
   local.get $round
   i32.const 1
   i32.add
   local.tee $round
   i32.const 16
   i32.lt_u
   br_if $mix)
  local.get $x
  local.get $y
  i32.xor))
