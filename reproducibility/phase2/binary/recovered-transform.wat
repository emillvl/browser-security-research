(module
  (type (;0;) (func (param i32 i32) (result i32)))
  (func (;0;) (type 0) (param i32 i32) (result i32)
    (local i32)
    loop  ;; label = @1
      local.get 0
      local.get 1
      i32.xor
      i32.const 7
      i32.rotl
      i32.const 1664525
      i32.mul
      i32.const 1013904223
      i32.add
      local.set 0
      local.get 1
      local.get 0
      i32.const 13
      i32.rotr
      i32.xor
      local.set 1
      local.get 2
      i32.const 1
      i32.add
      local.tee 2
      i32.const 16
      i32.lt_u
      br_if 0 (;@1;)
    end
    local.get 0
    local.get 1
    i32.xor)
  (export "transform" (func 0)))
