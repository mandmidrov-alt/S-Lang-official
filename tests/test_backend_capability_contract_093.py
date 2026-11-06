from slang.backend import native_capabilities, mlir_toolchain_status

def test_native_capability_contract_is_explicit():
    caps = native_capabilities()
    assert caps.supports_type("Number")
    assert caps.supports_operation("reduce")
    assert caps.supports_memory_model("scalar-accumulator")
    assert caps.supports_fusion("fused-filter-map-reduce")
    assert "slang_reduce_f64" in caps.runtime_features

def test_mlir_capability_contract_is_explicit():
    caps = mlir_toolchain_status()
    assert caps.supports_type("Number")
    assert caps.supports_operation("physics.gravity")
    assert caps.supports_memory_model("memref")
    assert caps.supports_fusion("fused-filter-map-reduce")
    assert "mlir-scf" in caps.runtime_features
