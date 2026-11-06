#ifndef SLANG_OPS_TD
#define SLANG_OPS_TD
include "mlir/IR/OpBase.td"

def Slang_Dialect : Dialect {
  let name = "slang";
  let cppNamespace = "slang";
}

class Slang_Op<string mnemonic, list<Trait> traits = []> : Op<Slang_Dialect, mnemonic, traits>;

// Domain operation: this is the first operation with a real lowering path
// from the S-Lang dialect to standard SCF/Arith/Func operations.
def Slang_SimulateGravityOp : Slang_Op<"simulate_gravity", [Pure]> {
  let summary = "High-level deterministic gravity simulation";
  let arguments = (ins F64:$x, F64:$v, F64:$mass, F64:$gravity, F64:$dt, Index:$steps);
  let results = (outs F64:$x_out, F64:$v_out);
}


// Compiler-selected execution-region metadata. It is erased by the lowering
// pass after its mode has been materialized into standard MLIR structure.
def Slang_ExecutionRegionOp : Slang_Op<"execution_region", [Pure]> {
  let summary = "Selected execution-region metadata";
  let arguments = (ins);
  let results = (outs);
  let assemblyFormat = "attr-dict";
}

// Generic semantic operations are represented by a planning/result token in
// this first backend stage.  Their attributes preserve compiler decisions;
// later stages can replace the token with a concrete collection ABI.
class Slang_SemanticTokenOp<string mnemonic> : Slang_Op<mnemonic, [Pure]> {
  let arguments = (ins);
  let results = (outs I64:$result);
  let assemblyFormat = "attr-dict";
}

def Slang_FilterOp : Slang_SemanticTokenOp<"filter"> {
  let summary = "Semantic collection filter token";
}
def Slang_MapOp : Slang_SemanticTokenOp<"map"> {
  let summary = "Semantic collection map token";
}
def Slang_SortOp : Slang_SemanticTokenOp<"sort"> {
  let summary = "Semantic collection sort token";
}
def Slang_AggregateOp : Slang_SemanticTokenOp<"aggregate"> {
  let summary = "Semantic aggregate token";
}
def Slang_ReduceOp : Slang_SemanticTokenOp<"reduce"> {
  let summary = "Semantic reduce token";
}
def Slang_SequenceOp : Slang_SemanticTokenOp<"sequence"> {
  let summary = "Semantic sequence token";
}
def Slang_ChooseOp : Slang_SemanticTokenOp<"choose"> {
  let summary = "Semantic goal selection token";
}
def Slang_FindPathOp : Slang_SemanticTokenOp<"find_path"> {
  let summary = "Semantic graph path token";
}
def Slang_SatisfyOp : Slang_SemanticTokenOp<"satisfy"> {
  let summary = "Semantic constraint solving token";
}
#endif
