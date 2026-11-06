"""Semantic ExecutionIR -> MLIR textual lowering for S-Lang 0.81.

This stage deliberately emits an MLIR-level semantic representation.  It does
not claim that the out-of-tree C++ dialect lowers every emitted operation to
LLVM yet.  Scalar metadata is represented with standard MLIR types; collection
operations use the registered S-Lang dialect operations when the dialect
backend is present.
"""
from __future__ import annotations

from .compiler_pipeline import compile_semantic_pipeline
from .optimizer import _fuse_record_transform_pair
from .ast import Binary, Call, Field, Property, Compare, Logical, Conditional
import struct


def _esc(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"')


def _op_for_node(node):
    mapping = {
        "filter": "slang.filter",
        "map": "slang.map",
        "sort": "slang.sort",
        "aggregate": "slang.aggregate",
        "reduce": "slang.reduce",
        "sequence": "slang.sequence",
        "goal:select": "slang.choose",
        "goal:path": "slang.find_path",
        "goal:satisfy": "slang.satisfy",
        "physics.gravity": "slang.simulate_gravity",
        "binding": "slang.binding",
        "state:init": "slang.state_init",
        "state:set": "slang.state_set",
        "state:read": "slang.state_read",
        "effect:show": "slang.show",
    }
    return mapping.get(node.kind)


def _region_lowering_prefix(mode: str, index: int) -> list[str]:
    """Emit an explicit structural lowering anchor for one execution mode.

    These anchors are intentionally side-effect-free. They make the selected
    execution form visible to downstream MLIR passes without pretending that
    the semantic token operations already have a concrete collection ABI.
    """
    if mode == "streaming":
        return [
            f'    // execution-region {index}: streaming',
            f'    %stream_lb_{index} = arith.constant 0 : index',
            f'    %stream_ub_{index} = arith.constant 0 : index',
            f'    %stream_step_{index} = arith.constant 1 : index',
            f'    scf.for %stream_i_{index} = %stream_lb_{index} to %stream_ub_{index} step %stream_step_{index} {{',
            f'      // streaming region {index}: semantic operations are lowered here',
        ]
    if mode == "parallel":
        return [
            f'    // execution-region {index}: parallel',
            f'    // parallelism is an execution-form obligation; semantic collection work is not duplicated here',
            f'    %parallel_lb_{index} = arith.constant 0 : index',
            f'    %parallel_ub_{index} = arith.constant 0 : index',
            f'    %parallel_step_{index} = arith.constant 1 : index',
            f'    scf.parallel ( %parallel_lb_{index} ) = ( %parallel_lb_{index} ) to ( %parallel_ub_{index} ) step ( %parallel_step_{index} ) {{',
            f'      // parallel region {index}: scheduler-owned execution body',
        ]
    if mode == "materialized":
        return [
            f'    // execution-region {index}: materialized',
            f'    %materialized_{index} = memref.alloca() : memref<1xi64>',
        ]
    raise ValueError(f"unsupported execution mode '{mode}'")


def _region_lowering_suffix(mode: str, index: int) -> list[str]:
    if mode in {"streaming", "parallel"}:
        return [
            '      scf.yield' if mode == 'streaming' else '      scf.yield',
            '    }',
        ]
    if mode == "materialized":
        return [f'    memref.dealloc %materialized_{index} : memref<1xi64>']
    raise ValueError(f"unsupported execution mode '{mode}'")


_RUNTIME_ABI = {
    "filter": "slang_filter",
    "map": "slang_map",
    "sort": "slang_sort",
    "aggregate": "slang_aggregate",
    "reduce": "slang_reduce",
    "sequence": "slang_sequence",
    "goal:select": "slang_choose",
    "goal:path": "slang_find_path",
    "goal:satisfy": "slang_satisfy",
    "effect:show": "slang_show",
}


def _dependency_values(node, value_by_binding):
    values = []
    for dep in node.dependencies:
        value = value_by_binding.get(dep)
        if value is not None:
            values.append(value)
    return values


def _runtime_call(node, result_name, value_by_binding):
    """Lower a generic semantic node to the explicit S-Lang runtime ABI.

    The ABI deliberately uses opaque i64 handles at this stage.  This is a
    concrete MLIR operation (`func.call`), while the runtime owns the collection
    representation and operation semantics.  No semantic token operation is
    left behind for these nodes.
    """
    callee = _RUNTIME_ABI.get(node.kind)
    if callee is None:
        return None
    args = _dependency_values(node, value_by_binding)
    if not args:
        args = ["%zero"]
    return f'{{result}} = func.call @{callee}({", ".join(args)}) : ({", ".join(["i64"] * len(args))}) -> i64'.format(result=result_name)


def _literal_f64_rows(module, name):
    for ds in getattr(module, "datasets", ()):
        if ds.name != name:
            continue
        values=[]
        for row in ds.rows:
            value=row.get("value")
            if isinstance(value, (int,float)) and not isinstance(value,bool):
                values.append(float(value))
            else:
                return None
        return values
    return None

def _literal_record_rows(module, name):
    """Return (record_name, rows) for a literal list of record constructors."""
    for binding in getattr(module, "bindings", ()):
        if binding.name != name:
            continue
        expr = binding.expr
        rows = getattr(expr, "value", None)
        if not isinstance(rows, list) or not rows:
            return None
        if not all(getattr(x, "name", None) for x in rows):
            return None
        record_name = rows[0].name
        if any(x.name != record_name for x in rows):
            return None
        return record_name, rows
    return None

def _literal_number(expr):
    value=getattr(expr, "value", None)
    if isinstance(value, (int,float)) and not isinstance(value,bool):
        return float(value)
    return None

def _compare_code(expr):
    return {">":0, ">=":1, "<":2, "<=":3, "==":4, "!=":5}.get(getattr(expr, "op", None))

def _simple_filter_spec(op):
    pred=getattr(op, "predicate", None)
    expr=getattr(pred, "expr", None)
    if expr is None or _compare_code(expr) is None:
        return None
    left=getattr(expr, "left", None); right=getattr(expr, "right", None)
    if getattr(left, "name", None) in {"value", "item"}:
        number=_literal_number(right)
        if number is not None: return number, _compare_code(expr)
    if getattr(right, "name", None) in {"value", "item"}:
        number=_literal_number(left)
        if number is not None:
            # Reverse comparison direction.
            return number, {0:2,1:3,2:0,3:1,4:4,5:5}[_compare_code(expr)]
    return None

def _simple_sort_spec(op):
    expr = getattr(getattr(op, "spec", None), "expr", None)
    # The compact f64 collection ABI can sort scalar values directly.
    # Record/row field keys require the generic semantic ABI unless a
    # record-specific lowering has already handled them.
    return getattr(expr, "name", None) in {"value", "item"}


def _simple_map_spec(op):
    expr=getattr(op, "expr", None)
    if expr is None: return None
    left=getattr(expr, "left", None); right=getattr(expr, "right", None)
    for element, other in ((left,right),(right,left)):
        if getattr(element, "name", None) in {"value", "item"}:
            number=_literal_number(other)
            if number is not None and getattr(expr, "op", None) in {"*","+","-","/","^"}:
                code={"*":0,"+":1,"-":2,"/":3,"^":4}[expr.op]
                if element is right and expr.op in {"-","/"}:
                    return number, code, True
                return number, code, False
    return None



def _f64_bits(value):
    return struct.unpack("q", struct.pack("d", float(value)))[0]


def _record_bool_program(expr, schema):
    """Compile a supported row predicate to postfix 5-word runtime bytecode."""
    words = []
    def emit(e):
        if isinstance(e, Logical):
            if e.op == "not":
                emit(e.left); words.extend([5, 0, 0, 0, 0]); return True
            if e.op in {"and", "or"}:
                if not emit(e.left) or not emit(e.right): return False
                words.extend([3 if e.op == "and" else 4, 0, 0, 0, 0]); return True
            return False
        if isinstance(e, Compare):
            code = _compare_code(e)
            if code is None: return False
            lf = _record_field_expr_spec(e.left, schema); rf = _record_field_expr_spec(e.right, schema)
            if lf is not None:
                n = _literal_number(e.right)
                if n is not None:
                    words.extend([1, lf, -1, code, _f64_bits(n)]); return True
            if rf is not None:
                n = _literal_number(e.left)
                if n is not None:
                    rev = {0:2,1:3,2:0,3:1,4:4,5:5}[code]
                    words.extend([1, rf, -1, rev, _f64_bits(n)]); return True
            if lf is not None and rf is not None:
                words.extend([2, lf, rf, code, _f64_bits(1.0)]); return True
            # field > field * constant (and equivalent / constant)
            if isinstance(e.right, Binary) and e.right.op in {"*", "/"}:
                base = _record_field_expr_spec(e.left, schema)
                other = _record_field_expr_spec(e.right.left, schema)
                n = _literal_number(e.right.right)
                if base is not None and other is not None and n is not None:
                    mult = n if e.right.op == "*" else (1.0 / n)
                    words.extend([2, base, other, code, _f64_bits(mult)]); return True
            return False
        if getattr(e, "value", None) is True or getattr(e, "value", None) is False:
            words.extend([0, 1 if e.value else 0, 0, 0, 0]); return True
        return False
    return words if emit(expr) else None


def _record_numeric_program(expr, schema):
    """Compile a numeric/conditional row expression to postfix runtime bytecode."""
    words=[]
    arith={"+":3,"-":4,"*":5,"/":6,"^":7}
    cmpops={">":10,">=":11,"<":12,"<=":13,"==":14,"!=":15}
    logical={"and":16,"or":17}
    def emit(e):
        if isinstance(e, (Field, Property)):
            fi=_record_field_expr_spec(e, schema)
            if fi is None: return False
            words.extend([1, fi, 0, 0, 0]); return True
        if getattr(e, "value", None) is not None and isinstance(getattr(e,"value",None),(int,float)) and not isinstance(e.value,bool):
            words.extend([2,0,0,0,_f64_bits(e.value)]); return True
        if isinstance(e, Binary) and e.op in arith:
            if not emit(e.left) or not emit(e.right): return False
            words.extend([arith[e.op],0,0,0,0]); return True
        if isinstance(e, Compare):
            if not emit(e.left) or not emit(e.right): return False
            words.extend([cmpops[e.op],0,0,0,0]); return True
        if isinstance(e, Logical):
            if e.op == "not":
                if not emit(e.left): return False
                words.extend([18,0,0,0,0]); return True
            if e.op in logical:
                if not emit(e.left) or not emit(e.right): return False
                words.extend([logical[e.op],0,0,0,0]); return True
            return False
        if isinstance(e, Conditional):
            if not emit(e.condition) or not emit(e.then_expr) or not emit(e.else_expr): return False
            words.extend([8,0,0,0,0]); return True
        return False
    return words if emit(expr) else None


def _record_mixed_program(expr, schema, text_pool):
    """Compile a typed Number/Boolean/Text row expression to postfix bytecode."""
    words=[]
    arith={"+":4,"-":5,"*":6,"/":7,"^":8}
    cmpops={">":10,">=":11,"<":12,"<=":13,"==":14,"!=":15}
    type_code={"Number":0,"Boolean":1,"Text":2}

    def field_type(e):
        if not isinstance(e,(Field,Property)): return None
        fi=_record_field_expr_spec(e,schema)
        if fi is None: return None
        fields=getattr(schema,"fields",())
        return fields[fi].type_name if 0 <= fi < len(fields) else None

    def emit(e):
        if isinstance(e,(Field,Property)):
            fi=_record_field_expr_spec(e,schema); typ=field_type(e)
            if fi is None or typ not in type_code: return False
            words.extend([3,fi,type_code[typ],0,0]); return True
        value=getattr(e,"value",None)
        if isinstance(value,bool):
            words.extend([0,1 if value else 0,0,0,0]); return True
        if isinstance(value,(int,float)) and not isinstance(value,bool):
            words.extend([1,0,0,0,_f64_bits(value)]); return True
        if isinstance(value,str):
            idx=len(text_pool); text_pool.append(value)
            words.extend([23,idx,0,0,0]); return True
        if isinstance(e,Binary) and e.op in arith:
            if not emit(e.left) or not emit(e.right): return False
            words.extend([arith[e.op],0,0,0,0]); return True
        if isinstance(e,Compare):
            lt,rt=field_type(e.left),field_type(e.right)
            # Text comparisons are deliberately limited to equality/inequality.
            if lt == "Text" or rt == "Text":
                if e.op not in {"==","!="}: return False
                if not emit(e.left) or not emit(e.right): return False
                words.extend([21 if e.op == "==" else 22,0,0,0,0]); return True
            if lt == "Boolean" or rt == "Boolean":
                if e.op not in {"==","!="}: return False
                if not emit(e.left) or not emit(e.right): return False
                words.extend([24 if e.op == "==" else 25,0,0,0,0]); return True
            if not emit(e.left) or not emit(e.right): return False
            code=cmpops.get(e.op)
            if code is None: return False
            words.extend([code,0,0,0,0]); return True
        if isinstance(e,Logical):
            if e.op == "not":
                if not emit(e.left): return False
                words.extend([18,0,0,0,0]); return True
            if e.op in {"and","or"}:
                if not emit(e.left) or not emit(e.right): return False
                words.extend([16 if e.op == "and" else 17,0,0,0,0]); return True
        if isinstance(e,Conditional):
            if not emit(e.condition) or not emit(e.then_expr) or not emit(e.else_expr): return False
            words.extend([19,0,0,0,0]); return True
        return False
    return words if emit(expr) else None


def _emit_record_text_pool(texts, name):
    """Materialize a temporary i64 table of C-string pointers for mixed ABI."""
    lines=[]
    if not texts:
        return lines, "%zero", 0
    ptr_names=[]
    for i, value in enumerate(texts):
        encoded=value.encode("utf-8")
        # MLIR memref of i8 is used as an owned temporary. Runtime copies it.
        size=max(len(encoded)+1,1)
        buf=f"{name}_str_{i}"
        lines.append(f"    {buf} = memref.alloca() : memref<{size}xi8>")
        for j,b in enumerate(encoded+b"\x00"):
            lines.append(f"    {name}_c_{i}_{j} = arith.constant {b} : i8")
            lines.append(f"    {name}_i_{i}_{j} = arith.constant {j} : index")
            lines.append(f"    memref.store {name}_c_{i}_{j}, {buf}[{name}_i_{i}_{j}] : memref<{size}xi8>")
        idx=f"{name}_pidx_{i}"; ptr=f"{name}_ptr_{i}"
        lines.append(f"    {idx} = memref.extract_aligned_pointer_as_index {buf}[] : memref<{size}xi8>")
        lines.append(f"    {ptr} = arith.index_cast {idx} : index to i64")
        ptr_names.append(ptr)
    table=f"{name}_table"; cap=max(len(ptr_names),1)
    lines.append(f"    {table} = memref.alloca() : memref<{cap}xi64>")
    for i,ptr in enumerate(ptr_names):
        ii=f"{name}_ti_{i}"; lines.append(f"    {ii} = arith.constant {i} : index")
        lines.append(f"    memref.store {ptr}, {table}[{ii}] : memref<{cap}xi64>")
    idx=f"{name}_table_idx"; out=f"{name}_table_ptr"
    lines.append(f"    {idx} = memref.extract_aligned_pointer_as_index {table}[] : memref<{cap}xi64>")
    lines.append(f"    {out} = arith.index_cast {idx} : index to i64")
    return lines,out,len(ptr_names)

def _record_expr_needs_generic(expr):
    if isinstance(expr, (Conditional, Logical)):
        return True
    if isinstance(expr, Binary):
        return _record_expr_needs_generic(expr.left) or _record_expr_needs_generic(expr.right)
    if isinstance(expr, Compare):
        return _record_expr_needs_generic(expr.left) or _record_expr_needs_generic(expr.right)
    return False


def _emit_record_program(words, name):
    """Return MLIR lines that materialize i64 postfix bytecode and its pointer."""
    size=max(len(words),1)
    lines=[f"    {name}_buf = memref.alloca() : memref<{size}xi64>"]
    for i, word in enumerate(words):
        lines.append(f"    {name}_v{i} = arith.constant {int(word)} : i64")
        lines.append(f"    {name}_i{i} = arith.constant {i} : index")
        lines.append(f"    memref.store {name}_v{i}, {name}_buf[{name}_i{i}] : memref<{size}xi64>")
    idx=f"{name}_ptridx"; ptr=f"{name}_ptr"
    lines.append(f"    {idx} = memref.extract_aligned_pointer_as_index {name}_buf[] : memref<{size}xi64>")
    lines.append(f"    {ptr} = arith.index_cast {idx} : index to i64")
    return lines, ptr, len(words)//5

def _emit_record_multi_map_program(expressions, schema, result_name):
    """Build one postfix program that computes and stores multiple record fields."""
    words=[]
    for target, expr in expressions:
        program=_record_numeric_program(expr, schema)
        if program is None:
            return None
        words.extend(program)
        words.extend([20, target, 0, 0, 0])
    if not words:
        return None
    return _emit_record_program(words, result_name)

def _emit_record_mixed_multi_map_program(expressions, schema, result_name):
    """Build one unified mixed Record transform program.

    A target field may be a direct source-field projection/reordering or a
    computed expression. Direct copies use opcode 26 so the runtime can copy
    the typed field without pushing it through the expression stack. Both
    forms remain in the same schema-changing transformation call.
    """
    words=[]; text_pool=[]
    for target, expr in expressions:
        direct=_record_field_expr_spec(expr, schema)
        if direct is not None:
            words.extend([26, target, direct, 0, 0])
            continue
        program=_record_mixed_program(expr, schema, text_pool)
        if program is None: return None
        words.extend(program); words.extend([20,target,0,0,0])
    if not words: return None
    plines, pptr, plen = _emit_record_program(words, result_name + "_prog")
    tlines, tptr, tcount = _emit_record_text_pool(text_pool, result_name + "_texts")
    return tlines + plines, pptr, plen, tptr, tcount

def _emit_record_mixed_index_table(indices, name):
    """Materialize a deterministic i64 source-field index table."""
    size=max(len(indices),1)
    lines=[f"    {name}_fields = memref.alloca() : memref<{size}xi64>"]
    for i, value in enumerate(indices):
        vi=f"{name}_field_{i}"; ii=f"{name}_field_i_{i}"
        lines.append(f"    {vi} = arith.constant {int(value)} : i64")
        lines.append(f"    {ii} = arith.constant {i} : index")
        lines.append(f"    memref.store {vi}, {name}_fields[{ii}] : memref<{size}xi64>")
    idx=f"{name}_fields_idx"; ptr=f"{name}_fields_ptr"
    lines.append(f"    {idx} = memref.extract_aligned_pointer_as_index {name}_fields[] : memref<{size}xi64>")
    lines.append(f"    {ptr} = arith.index_cast {idx} : index to i64")
    return lines, ptr, len(indices)

def _emit_record_mixed_type_table(schema, name):
    """Materialize target Record field type tags for the mixed ABI."""
    fields=getattr(schema, "fields", ()) if schema is not None else ()
    type_code={"Number":0,"Boolean":1,"Text":2}
    buf=f"{name}_types"
    lines=[f"    {buf} = memref.alloca() : memref<{max(len(fields),1)}xi64>"]
    for i,field in enumerate(fields):
        code=type_code.get(getattr(field,"type_name",None))
        if code is None:
            raise ValueError(f"MLIR mixed record ABI does not support field type '{getattr(field,'type_name',None)}'")
        vi=f"{name}_type_{i}"; ii=f"{name}_type_i_{i}"
        lines.append(f"    {vi} = arith.constant {code} : i64")
        lines.append(f"    {ii} = arith.constant {i} : index")
        lines.append(f"    memref.store {vi}, {buf}[{ii}] : memref<{max(len(fields),1)}xi64>")
    idx=f"{name}_types_idx"; ptr=f"{name}_types_ptr"
    lines.append(f"    {idx} = memref.extract_aligned_pointer_as_index {buf}[] : memref<{max(len(fields),1)}xi64>")
    lines.append(f"    {ptr} = arith.index_cast {idx} : index to i64")
    return lines, ptr, len(fields)

def _record_field_index(schema, field_name):
    if schema is None:
        return None
    for i, field in enumerate(getattr(schema, "fields", ())):
        if field.name == field_name:
            return i
    return None

def _simple_record_filter_spec(op, schema):
    expr=getattr(getattr(op, "predicate", None), "expr", None)
    if expr is None or getattr(expr, "op", None) not in {">",">=","<","<=","==","!="}:
        return None
    left=getattr(expr,"left",None); right=getattr(expr,"right",None)
    for field_expr, other, reverse in ((left,right,False),(right,left,True)):
        base=getattr(field_expr,"base",None)
        field=getattr(field_expr,"name",None)
        if getattr(base,"name",None) not in {"row","item"} or field is None:
            continue
        number=_literal_number(other)
        fi=_record_field_index(schema, field)
        if number is None or fi is None:
            continue
        code=_compare_code(expr)
        if reverse:
            code={0:2,1:3,2:0,3:1,4:4,5:5}[code]
        return fi, number, code
    return None

def _simple_record_map_spec(op, schema):
    expr=getattr(op,"expr",None)
    # Direct field projection or one-field arithmetic update.
    if isinstance(expr, Call):
        return None
    base=getattr(expr,"base",None); field=getattr(expr,"name",None)
    if getattr(base,"name",None) not in {"row","item"} or field is None:
        return None
    fi=_record_field_index(schema, field)
    if fi is None:
        return None
    return fi, None, None

def _record_constructor_map_specs(op, input_schema, output_schema):
    expr=getattr(op,"expr",None)
    if not isinstance(expr, Call) or input_schema is None or output_schema is None:
        return None
    out_fields=getattr(output_schema,"fields",())
    in_fields=getattr(input_schema,"fields",())
    in_index={f.name:i for i,f in enumerate(in_fields)}
    specs=[]
    for out_index, arg in enumerate(getattr(expr,"args",())):
        if out_index >= len(out_fields):
            return None
        if out_fields[out_index].type_name != "Number":
            return None
        if isinstance(arg, (Field, Property)) and getattr(getattr(arg,"base",None),"name",None) in {"row","item"}:
            fi=in_index.get(arg.name)
            if fi is None: return None
            specs.append((out_index,fi,None,0))
            continue
        # Only simple row.field +/- constant is representable by map_field.
        if isinstance(arg, Binary) and arg.op in {"+","-","*","/","^"}:
            left,right=arg.left,arg.right
            lf = _record_field_expr_spec(left, input_schema); rf = _record_field_expr_spec(right, input_schema)
            if lf is not None and rf is not None and arg.op in {"+","-","*","/"}:
                specs.append((out_index, lf, ("field", rf), {"+":5,"-":6,"*":7,"/":8}[arg.op])); continue
            for field_expr, other, reversed_operands in ((left,right,False),(right,left,True)):
                if isinstance(field_expr,(Field,Property)) and getattr(getattr(field_expr,"base",None),"name",None) in {"row","item"}:
                    fi=in_index.get(field_expr.name); number=_literal_number(other)
                    if fi is None or number is None or reversed_operands and arg.op in {"-","/"}: return None
                    code={"*":0,"+":1,"-":2,"/":3,"^":4}[arg.op]
                    specs.append((out_index,fi,number,code)); break
            else:
                return None
            continue
        return None
    if len(specs) != len(out_fields) or len(out_fields) != len(in_fields):
        return None
    # The current ABI preserves column positions; require same schema shape.
    if tuple(f.name for f in out_fields) != tuple(f.name for f in in_fields):
        return None
    return specs

def _record_field_expr_spec(expr, schema):
    if not isinstance(expr, (Field, Property)):
        return None
    if getattr(getattr(expr, "base", None), "name", None) not in {"row", "item"}:
        return None
    fi = _record_field_index(schema, getattr(expr, "name", None))
    return fi

def _record_compare_spec(expr, schema):
    if not isinstance(expr, Compare):
        return None
    code = _compare_code(expr)
    left, right = expr.left, expr.right
    lfi = _record_field_expr_spec(left, schema); rfi = _record_field_expr_spec(right, schema)
    if lfi is not None and rfi is not None:
        return ("field", lfi, rfi, 1.0, code)
    if lfi is not None:
        n = _literal_number(right)
        if n is not None: return ("const", lfi, n, code)
    if rfi is not None:
        n = _literal_number(left)
        if n is not None:
            return ("const", rfi, n, {0:2,1:3,2:0,3:1,4:4,5:5}[code])
    # field > field * constant
    if isinstance(right, Binary) and right.op in {"*", "/"} and _record_field_expr_spec(left, schema) is not None:
        fi = _record_field_expr_spec(left, schema)
        rf = _record_field_expr_spec(right.left, schema); n = _literal_number(right.right)
        if rf is not None and n is not None:
            mult = n if right.op == "*" else (1.0 / n)
            return ("field", fi, rf, mult, code)
    return None

def _record_filter_expr_calls(expr, schema, current_name):
    if isinstance(expr, Logical) and expr.op == "and":
        calls=[]
        calls.extend(_record_filter_expr_calls(expr.left, schema, current_name))
        calls.extend(_record_filter_expr_calls(expr.right, schema, current_name))
        return calls
    spec = _record_compare_spec(expr, schema)
    if spec is None: return None
    if spec[0] == "const":
        _, fi, n, code = spec
        return [("const", fi, n, code)]
    _, lfi, rfi, mult, code = spec
    return [("field", lfi, rfi, mult, code)]


def _resolve_record_expr_to_root(expr, current_result, ast_by_result, schema_by_result, seen=()):
    """Resolve Record-map field references through a same-shape map chain.

    Returns ``(resolved_expr, root_result, root_schema)``.  Only row/item/value
    field references are substituted; opaque calls and unsupported schema
    changes stop resolution conservatively.
    """
    if current_result in seen:
        return expr, current_result, schema_by_result.get(current_result, (None, None))[0]
    ast_op = ast_by_result.get(current_result)
    source_result = getattr(ast_op, 'source', None) if ast_op is not None else None
    node_pair = schema_by_result.get(current_result, (None, None))
    current_input = node_pair[0]
    if source_result is None or source_result not in ast_by_result:
        return expr, source_result or current_result, current_input
    source_pair = schema_by_result.get(source_result, (None, None))
    source_output = source_pair[1]
    source_ast = ast_by_result.get(source_result)
    source_expr = getattr(source_ast, 'expr', None)
    if not isinstance(source_expr, Call) or source_output is None:
        return expr, source_result, source_pair[0]
    in_fields = tuple(getattr(source_pair[0], 'fields', ()) or ())
    out_fields = tuple(getattr(source_output, 'fields', ()) or ())
    args = tuple(getattr(source_expr, 'args', ()) or ())
    if len(args) != len(out_fields) or not in_fields:
        return expr, source_result, source_pair[0]
    out_index = {str(f.name): i for i, f in enumerate(out_fields)}
    in_names = {str(f.name) for f in in_fields}

    def walk(node):
        if isinstance(node, Field) and getattr(node.base, 'name', None) in {'row', 'item', 'value'}:
            field_name = str(node.name)
            if field_name not in out_index:
                return node
            arg = args[out_index[field_name]]
            resolved_arg, root_result, root_schema = _resolve_record_expr_to_root(
                arg, source_result, ast_by_result, schema_by_result, seen + (current_result,)
            )
            return resolved_arg
        if isinstance(node, Binary):
            return Binary(node.op, walk(node.left), walk(node.right))
        if isinstance(node, Compare):
            return Compare(node.op, walk(node.left), walk(node.right))
        if isinstance(node, Logical):
            return Logical(node.op, walk(node.left), walk(node.right) if node.right is not None else None)
        if isinstance(node, Conditional):
            return Conditional(walk(node.condition), walk(node.then_expr), walk(node.else_expr))
        if isinstance(node, Call):
            return Call(node.name, tuple(walk(a) for a in node.args))
        if isinstance(node, Property):
            return Property(walk(node.base), node.name)
        return node

    resolved = walk(expr)
    # Find the root by following the source chain independently of whether the
    # current expression happened to contain a field reference.
    root_result = source_result
    root_schema = source_pair[0]
    probe = source_result
    seen_chain = set(seen)
    while probe not in seen_chain:
        seen_chain.add(probe)
        probe_ast = ast_by_result.get(probe)
        nxt = getattr(probe_ast, 'source', None) if probe_ast is not None else None
        if nxt is None:
            break
        pair = schema_by_result.get(nxt, (None, None))
        if nxt not in ast_by_result:
            # External/root collection: its schema is the input schema of the
            # first map in the chain.
            root_result, root_schema = nxt, schema_by_result.get(probe, (None, None))[0]
            break
        if not isinstance(getattr(ast_by_result.get(nxt), 'expr', None), Call) or pair[1] is None:
            root_result, root_schema = nxt, pair[1] or pair[0]
            break
        root_result, root_schema = nxt, pair[0]
        probe = nxt
    return resolved, root_result, root_schema


def _same_record_shape(schema_a, schema_b):
    af = tuple(getattr(schema_a, 'fields', ()) or ())
    bf = tuple(getattr(schema_b, 'fields', ()) or ())
    return bool(af) and len(af) == len(bf) and tuple((f.name, f.type_name) for f in af) == tuple((f.name, f.type_name) for f in bf)


def _emit_record_recompute_chain(root_result, target_result, ast_by_result, schema_by_result,
                                 value_by_binding, retained_root_names, result_name):
    """Rebuild a same-shape Record producer chain from minimal root fields."""
    chain=[]
    cur=target_result
    seen=set()
    while cur and cur not in seen:
        seen.add(cur); chain.append(cur)
        if cur == root_result: break
        if cur not in ast_by_result:
            break
        cur=getattr(ast_by_result.get(cur), 'source', None)
    if not chain or chain[-1] != root_result:
        # The root may be an external collection not represented in ast_by_result.
        if root_result in seen and root_result not in ast_by_result:
            pass
        else:
            return None
    chain=list(reversed(chain))
    root_source=value_by_binding.get(root_result)
    root_pair=schema_by_result.get(root_result, (None, None))
    root_schema=root_pair[0]
    if root_schema is None and len(chain) > 1:
        root_schema=schema_by_result.get(chain[1], (None, None))[0]
    if root_source is None or root_schema is None:
        return None
    root_fields=tuple(getattr(root_schema, 'fields', ()) or ())
    retained_indices=[i for i,f in enumerate(root_fields) if str(f.name) in retained_root_names]
    current=root_source
    lines=[]
    if retained_indices and len(retained_indices) < len(root_fields):
        ibuf=f"{result_name}_chain_fields"
        lines=[f"    {ibuf} = memref.alloca() : memref<{len(retained_indices)}xi64>"]
        for i,fi in enumerate(retained_indices):
            lines.append(f"    %chain_c_{result_name}_{i} = arith.constant {fi} : i64")
            lines.append(f"    %chain_i_{result_name}_{i} = arith.constant {i} : index")
            lines.append(f"    memref.store %chain_c_{result_name}_{i}, {ibuf}[%chain_i_{result_name}_{i}] : memref<{len(retained_indices)}xi64>")
        ridx=f"{result_name}_chain_idx"; rptr=f"{result_name}_chain_ptr"
        lines.append(f"    {ridx} = memref.extract_aligned_pointer_as_index {ibuf}[] : memref<{len(retained_indices)}xi64>")
        lines.append(f"    {rptr} = arith.index_cast {ridx} : index to i64")
        mixed=any(getattr(f,'type_name',None)!='Number' for f in root_fields)
        callee='slang_record_mixed_mask_fields' if mixed else 'slang_record_f64_mask_fields'
        masked=f"{result_name}_chain_masked"
        lines.append(f"    {masked} = func.call @{callee}({current}, {rptr}, {len(retained_indices)}) : (i64, i64, i64) -> i64")
        current=masked
    for idx,res in enumerate(chain):
        if res == root_result:
            continue
        ast_op=ast_by_result.get(res)
        expr=getattr(ast_op,'expr',None)
        pair=schema_by_result.get(res,(None,None)); in_schema,out_schema=pair
        if not isinstance(expr, Call) or not _same_record_shape(in_schema,out_schema):
            return None
        args=tuple(getattr(expr,'args',()) or ())
        out_fields=tuple(getattr(out_schema,'fields',()) or ())
        changed=[]
        for oi,arg in enumerate(args):
            direct=_record_field_expr_spec(arg,in_schema)
            if direct == oi: continue
            changed.append((oi,arg))
        if not changed:
            continue
        mixed=any(getattr(f,'type_name',None)!='Number' for f in tuple(getattr(in_schema,'fields',()) or ()))
        if mixed:
            emitted=_emit_record_mixed_multi_map_program(changed,in_schema,f"{result_name}_chain_{idx}")
            if not emitted: return None
            plines,pptr,plen,tptr,tcount=emitted
            lines.extend(plines)
            nxt=f"{result_name}_chain_{idx}_v"
            lines.append(f"    {nxt} = func.call @slang_record_mixed_map_fields_expr({current}, {pptr}, {plen}, {tptr}, {tcount}) : (i64, i64, i64, i64, i64) -> i64")
        else:
            emitted=_emit_record_multi_map_program(changed,in_schema,f"{result_name}_chain_{idx}")
            if not emitted: return None
            plines,pptr,plen=emitted
            lines.extend(plines)
            nxt=f"{result_name}_chain_{idx}_v"
            lines.append(f"    {nxt} = func.call @slang_record_f64_map_fields_expr({current}, {pptr}, {plen}) : (i64, i64, i64) -> i64")
        current=nxt
    return lines,current

def _runtime_collection_call(node, result_name, value_by_binding, module, ast_by_result, concrete_bindings, source_override=None):
    deps=_dependency_values(node, value_by_binding)
    ast_op=ast_by_result.get(node.result)
    source_binding=getattr(ast_op, "source", None) if ast_op is not None else None
    # ExecutionIR intentionally models source datasets as external inputs, so
    # the first collection node may have no graph dependency. Reconnect that
    # source here using the already-materialized dataset handle.
    if source_override is not None:
        deps=[source_override] + list(deps[1:]) if deps else [source_override]
    elif not deps and source_binding in value_by_binding:
        deps=[value_by_binding[source_binding]]
    kind=node.kind
    source_is_concrete = (
        source_binding in concrete_bindings
        or source_binding in value_by_binding
        or any(dep in concrete_bindings for dep in node.dependencies)
    )
    in_schema = getattr(node, "input_schema", None)
    out_schema = getattr(node, "output_schema", None)
    source_schema = in_schema
    # 1.10.42: concrete record chains use the record ABI directly. The source
    # handle is already materialized; field indices come from the semantic
    # schema, never from AST re-inference.
    if source_is_concrete and source_binding is not None and source_schema is not None:
        mixed_record = any(getattr(f, "type_name", None) != "Number" for f in getattr(source_schema, "fields", ()))
        if mixed_record and kind == "filter":
            expr = getattr(getattr(ast_by_result.get(node.result), "predicate", None), "expr", None)
            text_pool=[]
            program=_record_mixed_program(expr, source_schema, text_pool) if expr is not None else None
            if program and deps:
                plines, pptr, plen = _emit_record_program(program, result_name + "_mixed_pred")
                tlines, tptr, tcount = _emit_record_text_pool(text_pool, result_name + "_mixed_texts")
                return "\n".join(tlines + plines + [f"{result_name} = func.call @slang_record_mixed_filter_expr({deps[0]}, {pptr}, {plen}, {tptr}, {tcount}) : (i64, i64, i64, i64, i64) -> i64"])
        if kind == "filter":
            expr = getattr(getattr(ast_by_result.get(node.result), "predicate", None), "expr", None)
            program = _record_bool_program(expr, source_schema) if expr is not None and _record_expr_needs_generic(expr) else None
            if program and deps:
                plines, pptr, plen = _emit_record_program(program, result_name + "_pred")
                return "\n".join(plines + [f"{result_name} = func.call @slang_record_f64_filter_expr({deps[0]}, {pptr}, {plen}) : (i64, i64, i64) -> i64"])
            specs = _record_filter_expr_calls(expr, source_schema, result_name) if expr is not None else None
            if specs and deps:
                current = deps[0]; calls=[]
                for i, spec in enumerate(specs):
                    out = result_name if i == len(specs)-1 else f"{result_name}_f{i}"
                    if spec[0] == "const":
                        _, fi, threshold, code = spec
                        calls.append(f"{out} = func.call @slang_record_f64_filter({current}, {fi}, {threshold:g}, {code}) : (i64, i64, f64, i32) -> i64")
                    else:
                        _, lfi, rfi, mult, code = spec
                        calls.append(f"{out} = func.call @slang_record_f64_filter_field_compare({current}, {lfi}, {rfi}, {mult:g}, {code}) : (i64, i64, i64, f64, i32) -> i64")
                    current = out
                return "\n".join(calls)
        if mixed_record and kind == "map" and out_schema is not None:
            map_op = ast_by_result.get(node.result)
            if isinstance(getattr(map_op, "expr", None), Call) and deps:
                expr_call=map_op.expr; in_fields=getattr(source_schema,"fields",()); out_fields=getattr(out_schema,"fields",())
                args=list(getattr(expr_call,"args",()))
                # 1.10.47: a mixed Record constructor may now change record type/schema.
                # Every output field is evaluated against the original source schema.
                if len(args)==len(out_fields) and len(out_fields)>0:
                    same_shape=(len(in_fields)==len(out_fields) and tuple(f.name for f in in_fields)==tuple(f.name for f in out_fields) and tuple(f.type_name for f in in_fields)==tuple(f.type_name for f in out_fields))
                    if same_shape:
                        changed=[]
                        for oi,arg in enumerate(args):
                            direct=_record_field_expr_spec(arg,source_schema)
                            if direct == oi: continue
                            changed.append((oi,arg))
                        emitted=_emit_record_mixed_multi_map_program(changed,source_schema,result_name+"_mixed") if changed else None
                        if emitted:
                            plines,pptr,plen,tptr,tcount=emitted
                            return "\n".join(plines+[f"{result_name} = func.call @slang_record_mixed_map_fields_expr({deps[0]}, {pptr}, {plen}, {tptr}, {tcount}) : (i64, i64, i64, i64, i64) -> i64"])
                    # 1.10.50: a pure field projection/reordering needs no expression
                    # bytecode. Select source columns directly and let the semantic target
                    # schema remain authoritative.
                    if len(args)==len(out_fields) and len(args)>0:
                        projection=[]
                        projection_ok=True
                        for oi,arg in enumerate(args):
                            fi=_record_field_expr_spec(arg, source_schema)
                            if fi is None or getattr(source_schema.fields[fi], "type_name", None) != getattr(out_fields[oi], "type_name", None):
                                projection_ok=False; break
                            projection.append(fi)
                        if projection_ok:
                            ilines, iptr, icount = _emit_record_mixed_index_table(projection, result_name+"_projection")
                            type_lines, type_ptr, type_count = _emit_record_mixed_type_table(out_schema, result_name+"_projection")
                            return "\n".join(ilines+type_lines+[f"{result_name} = func.call @slang_record_mixed_project_fields({deps[0]}, {iptr}, {type_ptr}, {icount}) : (i64, i64, i64, i64) -> i64"])
                    # Schema-changing constructor: materialize the target type table and
                    # evaluate all constructor arguments, not just changed fields.
                    expressions=[(oi,arg) for oi,arg in enumerate(args)]
                    emitted=_emit_record_mixed_multi_map_program(expressions,source_schema,result_name+"_mixed_schema")
                    if emitted:
                        plines,pptr,plen,tptr,tcount=emitted
                        type_lines,type_ptr,type_count=_emit_record_mixed_type_table(out_schema,result_name+"_mixed_schema")
                        return "\n".join(type_lines+plines+[f"{result_name} = func.call @slang_record_mixed_map_to_schema_expr({deps[0]}, {type_ptr}, {type_count}, {pptr}, {plen}, {tptr}, {tcount}) : (i64, i64, i64, i64, i64, i64, i64) -> i64"])
        if kind == "map" and out_schema is not None:
            map_op = ast_by_result.get(node.result)
            if isinstance(getattr(map_op, "expr", None), Call) and deps:
                expr_call = map_op.expr
                in_fields = getattr(source_schema, "fields", ())
                out_fields = getattr(out_schema, "fields", ())
                if len(in_fields) == len(out_fields) and tuple(f.name for f in in_fields) == tuple(f.name for f in out_fields):
                    changed=[]
                    supported=True
                    for oi, arg in enumerate(getattr(expr_call, "args", ())):
                        direct = _record_field_expr_spec(arg, source_schema)
                        if direct == oi:
                            continue
                        if isinstance(arg, (Field, Property)) and direct is not None:
                            changed.append((oi, arg))
                            continue
                        changed.append((oi, arg))
                    emitted = _emit_record_multi_map_program(changed, source_schema, result_name + "_multi") if len(changed) >= 2 else None
                    if emitted:
                        plines, pptr, plen = emitted
                        return "\n".join(plines + [f"{result_name} = func.call @slang_record_f64_map_fields_expr({deps[0]}, {pptr}, {plen}) : (i64, i64, i64) -> i64"])
                    # One changed field keeps the existing specialized ABI path.
                    if len(changed) == 1:
                        arg = changed[0][1]
                        program = _record_numeric_program(arg, source_schema) if _record_expr_needs_generic(arg) else None
                        if program is not None:
                            plines, pptr, plen = _emit_record_program(program, f"{result_name}_expr")
                            return "\n".join(plines + [f"{result_name} = func.call @slang_record_f64_map_field_expr({deps[0]}, {changed[0][0]}, {pptr}, {plen}) : (i64, i64, i64, i64) -> i64"])
            specs = _record_constructor_map_specs(ast_by_result.get(node.result), source_schema, out_schema)
            if specs and deps:
                current = deps[0]
                calls=[]
                changed = [spec for spec in specs if spec[2] is not None]
                for call_index, (_out_index, field_index, operand, code) in enumerate(changed):
                    next_name = result_name if call_index == len(changed)-1 else f"{result_name}_r{call_index}"
                    if isinstance(operand, tuple) and operand[0] == "field":
                        bop = {5:0,6:1,7:2,8:3}[code]
                        calls.append(f"{next_name} = func.call @slang_record_f64_map_field_binary({current}, {field_index}, {operand[1]}, {bop}) : (i64, i64, i64, i32) -> i64")
                    else:
                        calls.append(f"{next_name} = func.call @slang_record_f64_map_field({current}, {field_index}, {operand:g}, {code}) : (i64, i64, f64, i32) -> i64")
                    current = next_name
                if calls:
                    return "\n".join(calls)
                return f"{result_name} = func.call @slang_record_f64_map_field({deps[0]}, 0, 0, 1) : (i64, i64, f64, i32) -> i64"
    if kind == "filter":
        op=ast_by_result.get(node.result)
        spec=_simple_filter_spec(op) if op else None
        if spec and deps and source_is_concrete:
            threshold, code=spec
            return f"{result_name} = func.call @slang_collection_f64_filter({deps[0]}, {threshold:g}, {code}) : (i64, f64, i32) -> i64"
    if kind == "map":
        op=ast_by_result.get(node.result)
        spec=_simple_map_spec(op) if op else None
        if spec and deps and not spec[2] and source_is_concrete:
            operand, code, _=spec
            return f"{result_name} = func.call @slang_collection_f64_map({deps[0]}, {operand:g}, {code}) : (i64, f64, i32) -> i64"
    if kind == "sort" and deps and source_is_concrete:
        op = ast_by_result.get(node.result)
        if _simple_sort_spec(op):
            return f"{result_name} = func.call @slang_collection_f64_sort({deps[0]}) : (i64) -> i64"
    if kind == "aggregate" and deps and source_is_concrete:
        op=ast_by_result.get(node.result)
        code={"sum":0,"min":1,"max":2,"count":3}.get(getattr(op,"operation",None))
        if code is not None:
            return f"{result_name} = func.call @slang_collection_f64_aggregate({deps[0]}, {code}) : (i64, i32) -> f64"
    # Generic ABI fallback: every semantic collection node must remain lowered
    # even when a specialized concrete ABI cannot represent its predicate/key.
    # This preserves the complete ExecutionIR dependency chain instead of
    # silently dropping an unsupported specialization.
    if kind in _RUNTIME_ABI and deps:
        callee = _RUNTIME_ABI[kind]
        return f"{result_name} = func.call @{callee}({', '.join(deps)}) : ({', '.join(['i64'] * len(deps))}) -> i64"
    return None



def _schema_storage_descriptors(schema_contract):
    """Return deterministic MLIR storage descriptors for record schemas.

    The semantic schema is authoritative.  Numeric fields get an f64 storage
    anchor; Boolean fields get i1; Text remains an opaque i64 handle until a
    concrete text runtime ABI is available.  These are backend storage
    descriptors, not claims that the buffers are already populated by the
    runtime collection ABI.
    """
    descriptors = []
    seen = set()
    for binding, input_schema, output_schema in schema_contract:
        for role, schema in (("input", input_schema), ("output", output_schema)):
            if schema is None:
                continue
            key = (binding, role, schema.name, tuple((f.name, f.type_name) for f in schema.fields))
            if key in seen:
                continue
            seen.add(key)
            fields = []
            for index, field in enumerate(schema.fields):
                if field.type_name == "Number":
                    storage = "f64"
                elif field.type_name == "Boolean":
                    storage = "i1"
                elif field.type_name == "Text":
                    storage = "i64"
                else:
                    storage = "i64"
                fields.append((index, field.name, field.type_name, storage))
            descriptors.append((binding, role, schema.name, tuple(fields)))
    return tuple(descriptors)

def _prepare_selected_record_lowering(module, selected):
    """Build backend-only fused Record maps from the authoritative selected plan."""
    record_plan = getattr(selected, "record_plan", None)
    if record_plan is None:
        return {}, set(), set()
    schemas = getattr(module, "_record_schemas", {}) or {}
    original = {op.result: op for op in getattr(module, "maps", ())}
    fused_final = {}
    skipped = set()
    boundaries = set(getattr(record_plan, "materialization_boundaries", ()) or ())
    # 1.10.79: a selected shared-recompute endpoint is a real backend reuse
    # point. If the structural optimizer fused through that endpoint, split the
    # backend fusion there so the endpoint is emitted once and every downstream
    # branch consumes the same runtime handle. This turns the shared-recompute
    # decision from metadata into an executable lowering constraint.
    shared_endpoints = {str(row[0]) for row in
                        (getattr(record_plan, "record_shared_recompute_decisions", ()) or ())}
    boundaries.update(shared_endpoints)
    for segment in getattr(record_plan, "fused_segments", ()):
        if len(segment) < 3:
            continue
        # Split only at selected shared endpoints that are internal to the
        # structural fusion segment. The endpoint itself remains the terminal
        # node of the first segment and therefore becomes an emitted handle.
        cuts = [i for i, name in enumerate(segment[1:-1], start=1)
                if str(name) in shared_endpoints]
        ranges = []
        start = 0
        for cut in cuts:
            ranges.append((start, cut + 1))
            start = cut
        ranges.append((start, len(segment) - 1))
        for a, b in ranges:
            part = segment[a:b + 1]
            if len(part) < 2:
                continue
            composed = original.get(part[1])
            if composed is None:
                continue
            ok = True
            for result_name in part[2:]:
                nxt = original.get(result_name)
                if nxt is None:
                    ok = False
                    break
                composed = _fuse_record_transform_pair(composed, nxt, schemas)
                if composed is None:
                    ok = False
                    break
            if ok:
                fused_final[part[-1]] = composed
                skipped.update(part[1:-1])
    # A selected materialization/shared boundary terminates the previous fused
    # segment; never skip the boundary node itself.
    skipped.difference_update(boundaries)
    return fused_final, skipped, boundaries


def lower_execution_ir_to_mlir(module, pipeline=None) -> str:
    """Lower selected ExecutionIR into concrete standard-MLIR operations.

    Generic semantic collection/goal tokens are replaced by calls to the
    explicit S-Lang runtime ABI.  Execution regions remain authoritative and
    determine the surrounding SCF/materialization structure.
    """
    pipeline = pipeline or compile_semantic_pipeline(module)
    ir = pipeline.optimized_ir
    selected = pipeline.selected_execution_plan
    type_contract = {binding: (input_type, output_type) for binding, input_type, output_type in ir.type_contract()}
    schema_contract = {binding: (input_schema, output_schema) for binding, input_schema, output_schema in ir.schema_contract()}
    schema_by_result = {node.result: (node.input_schema, node.output_schema) for node in ir.nodes}
    region_by_node = {node: region for region in selected.execution_regions for node in region.nodes}
    ast_by_result = {}
    for attr in ("filters", "maps", "sorts", "aggregates", "reduces"):
        for op in getattr(module, attr, ()):
            ast_by_result[op.result] = op
    record_fused_final, record_fused_intermediates, record_boundaries = _prepare_selected_record_lowering(module, selected)
    # The selected Record plan is authoritative. Backends consume its field-level
    # strategy contract rather than reconstructing projection/recompute choices.
    selected_record_field_strategies = tuple(getattr(getattr(selected, "record_plan", None), "field_strategies", ()) or ())
    selected_record_fanout_requirements = tuple(getattr(getattr(selected, "record_plan", None), "record_fanout_field_requirements", ()) or ())
    selected_record_shared_recompute = tuple(getattr(getattr(selected, "record_plan", None), "record_shared_recompute_decisions", ()) or ())
    shared_recompute_by_endpoint = {}
    for endpoint, field, source_fields, independent_cost, shared_cost in selected_record_shared_recompute:
        shared_recompute_by_endpoint.setdefault(str(endpoint), []).append(
            (str(field), tuple(source_fields), float(independent_cost), float(shared_cost))
        )
    fanout_fields_by_endpoint = {str(endpoint): tuple(fields) for endpoint, fields in selected_record_fanout_requirements}
    field_strategy_by_consumer = {}
    for endpoint, consumer, field, strategy, cost, source_fields in selected_record_field_strategies:
        consumer_key = consumer.split(":", 1)[0]
        field_strategy_by_consumer.setdefault(consumer_key, []).append(
            (field, strategy, cost, tuple(source_fields))
        )
        # Keep endpoint aliases available for synthetic/fused consumers whose
        # binding may differ from their semantic result name.
        field_strategy_by_consumer.setdefault(str(endpoint), []).append(
            (field, strategy, cost, tuple(source_fields))
        )
    declarations = [
        "  func.func private @slang_filter(%src: i64) -> i64",
        "  func.func private @slang_map(%src: i64) -> i64",
        "  func.func private @slang_sort(%src: i64) -> i64",
        "  func.func private @slang_aggregate(%src: i64) -> i64",
        "  func.func private @slang_reduce(%src: i64) -> i64",
        "  func.func private @slang_collection_f64_filter(%src: i64, %threshold: f64, %op: i32) -> i64",
        "  func.func private @slang_collection_f64_map(%src: i64, %operand: f64, %op: i32) -> i64",
        "  func.func private @slang_collection_f64_sort(%src: i64) -> i64",
        "  func.func private @slang_collection_f64_aggregate(%src: i64, %op: i32) -> f64",
        "  func.func private @slang_collection_f64_new(%ptr: i64, %count: i64) -> i64",
        "  func.func private @slang_record_f64_new(%columns: i64, %fields: i64, %rows: i64) -> i64",
        "  func.func private @slang_record_f64_new_flat(%data: i64, %fields: i64, %rows: i64) -> i64",
        "  func.func private @slang_record_f64_materialize(%src: i64) -> i64",
        "  func.func private @slang_record_f64_share(%src: i64) -> i64",
        "  func.func private @slang_record_f64_count(%src: i64) -> i64",
        "  func.func private @slang_record_f64_field_count(%src: i64) -> i64",
        "  func.func private @slang_record_f64_get(%src: i64, %field: i64, %row: i64) -> f64",
        "  func.func private @slang_record_f64_filter(%src: i64, %field: i64, %threshold: f64, %op: i32) -> i64",
        "  func.func private @slang_record_f64_filter_field_compare(%src: i64, %left: i64, %right: i64, %multiplier: f64, %op: i32) -> i64",
        "  func.func private @slang_record_f64_filter_expr(%src: i64, %program: i64, %instructions: i64) -> i64",
        "  func.func private @slang_record_f64_map_field_expr(%src: i64, %field: i64, %program: i64, %instructions: i64) -> i64",
        "  func.func private @slang_record_f64_map_fields_expr(%src: i64, %program: i64, %instructions: i64) -> i64",
        "  func.func private @slang_record_f64_mask_fields(%src: i64, %selected_fields: i64, %field_count: i64) -> i64",
        "  func.func private @slang_record_f64_map_field(%src: i64, %field: i64, %operand: f64, %op: i32) -> i64",
        "  func.func private @slang_record_f64_map_field_binary(%src: i64, %target: i64, %other: i64, %op: i32) -> i64",
        "  func.func private @slang_record_f64_free(%src: i64)",
        "  func.func private @slang_record_mixed_new_flat(%types: i64, %values: i64, %text_ptrs: i64, %fields: i64, %rows: i64) -> i64",
        "  func.func private @slang_record_mixed_materialize(%src: i64) -> i64",
        "  func.func private @slang_record_mixed_share(%src: i64) -> i64",
        "  func.func private @slang_record_mixed_count(%src: i64) -> i64",
        "  func.func private @slang_record_mixed_field_count(%src: i64) -> i64",
        "  func.func private @slang_record_mixed_field_type(%src: i64, %field: i64) -> i32",
        "  func.func private @slang_record_mixed_get_number(%src: i64, %field: i64, %row: i64) -> f64",
        "  func.func private @slang_record_mixed_get_bool(%src: i64, %field: i64, %row: i64) -> i32",
        "  func.func private @slang_record_mixed_get_text(%src: i64, %field: i64, %row: i64) -> i64",
        "  func.func private @slang_record_mixed_project_fields(%src: i64, %source_fields: i64, %target_types: i64, %target_fields: i64) -> i64",
        "  func.func private @slang_record_mixed_mask_fields(%src: i64, %selected_fields: i64, %field_count: i64) -> i64",
        "  func.func private @slang_record_mixed_filter_expr(%src: i64, %program: i64, %instructions: i64, %text_pool: i64, %text_count: i64) -> i64",
        "  func.func private @slang_record_mixed_map_fields_expr(%src: i64, %program: i64, %instructions: i64, %text_pool: i64, %text_count: i64) -> i64",
        "  func.func private @slang_record_mixed_map_to_schema_expr(%src: i64, %types: i64, %fields: i64, %program: i64, %instructions: i64, %text_pool: i64, %text_count: i64) -> i64",
        "  func.func private @slang_record_mixed_free(%src: i64)",
    ]

    lines = ["module {"]
    if selected_record_shared_recompute:
        for endpoint, field, source_fields, independent_cost, shared_cost in selected_record_shared_recompute:
            lines.append(
                f'  // S-Lang Record shared recompute: endpoint="{_esc(str(endpoint))}", field="{_esc(str(field))}", sources="{_esc(",".join(source_fields))}", independent_cost={independent_cost:g}, shared_cost={shared_cost:g}'
            )
    lines.extend(declarations)
    lines += ["  func.func @slang_program() -> i64 {", "    %zero = arith.constant 0 : i64"]
    value_by_binding = {}

    # 1.10.40: materialize the semantic record schema as a deterministic
    # backend storage plan.  Each field gets its own standard-MLIR memref
    # anchor; runtime population remains the responsibility of the concrete
    # record ABI and is therefore not implied by these anchors.
    storage_descriptors = _schema_storage_descriptors(tuple(ir.schema_contract()))
    storage_ids = {}
    storage_counter = 0
    for binding, role, schema_name, fields in storage_descriptors:
        base = binding.replace("#", "_").replace("-", "_")
        lines.append(f'    // record-schema-storage {base} {role} {schema_name}')
        field_map = []
        for index, field_name, type_name, storage in fields:
            storage_id = f"%schema_{storage_counter}"
            storage_counter += 1
            field_map.append(f"{field_name}:{type_name}->{storage_id}")
            if storage == "f64":
                lines.append(f"    {storage_id} = memref.alloca() : memref<1xf64>")
            elif storage == "i1":
                lines.append(f"    {storage_id} = memref.alloca() : memref<1xi1>")
            else:
                lines.append(f"    {storage_id} = memref.alloca() : memref<1xi64>")
            storage_ids[(binding, role, field_name)] = storage_id
        lines.append(f'    // schema-fields {base}: { _esc(";".join(field_map)) }')
        if all(storage == "f64" for _, _, _, storage in fields):
            lines.append(f'    // record-f64-abi {base}: filter/map preserve all {len(fields)} numeric columns')
    # 1.10.42 / 1.10.46 / 1.10.47: materialize literal Record collections. Numeric-only
    # schemas retain the compact f64 ABI; mixed Number/Boolean/Text schemas use
    # the typed mixed ABI and never coerce non-numeric fields to f64.
    for binding in getattr(module, "bindings", ()):
        literal = _literal_record_rows(module, binding.name)
        if literal is None:
            continue
        record_name, rows = literal
        record_decl = next((r for r in getattr(module, "records", ()) if r.name == record_name), None)
        if record_decl is None:
            continue
        if all(getattr(ft, "name", None) == "Number" for _, ft in record_decl.fields):
            total = len(rows) * len(record_decl.fields)
            buf = f"%record_flat_{len(value_by_binding)}"
            lines.append(f"    {buf} = memref.alloca() : memref<{max(total,1)}xf64>")
            for ri, row in enumerate(rows):
                for fi, arg in enumerate(row.args):
                    value = _literal_number(arg)
                    if value is None:
                        raise ValueError(f"MLIR numeric record ABI requires literal numeric field '{binding.name}'")
                    idx = ri * len(record_decl.fields) + fi
                    lines.append(f"    %record_c_{len(value_by_binding)}_{ri}_{fi} = arith.constant {value:g} : f64")
                    lines.append(f"    %record_i_{len(value_by_binding)}_{ri}_{fi} = arith.constant {idx} : index")
                    lines.append(f"    memref.store %record_c_{len(value_by_binding)}_{ri}_{fi}, {buf}[%record_i_{len(value_by_binding)}_{ri}_{fi}] : memref<{max(total,1)}xf64>")
            ptr_idx = f"%record_ptridx_{len(value_by_binding)}"; ptr_i64 = f"%record_ptr_{len(value_by_binding)}"
            lines.append(f"    {ptr_idx} = memref.extract_aligned_pointer_as_index {buf}[] : memref<{max(total,1)}xf64>")
            lines.append(f"    {ptr_i64} = arith.index_cast {ptr_idx} : index to i64")
            handle=f"%record_{len(value_by_binding)}"
            lines.append(f"    {handle} = func.call @slang_record_f64_new_flat({ptr_i64}, {len(record_decl.fields)}, {len(rows)}) : (i64, i64, i64) -> i64")
            value_by_binding[binding.name]=handle
            concrete_bindings=set(value_by_binding)
            continue
        fields=record_decl.fields; total=len(rows)*len(fields); tag=f"{len(value_by_binding)}"
        types_buf=f"%record_types_{tag}"; vals_buf=f"%record_values_{tag}"; text_buf=f"%record_texts_{tag}"
        lines.append(f"    {types_buf} = memref.alloca() : memref<{max(len(fields),1)}xi64>")
        lines.append(f"    {vals_buf} = memref.alloca() : memref<{max(total,1)}xi64>")
        lines.append(f"    {text_buf} = memref.alloca() : memref<{max(total,1)}xi64>")
        for fi,(_,ft) in enumerate(fields):
            typ={"Number":0,"Boolean":1,"Text":2}.get(ft.name)
            if typ is None: raise ValueError(f"MLIR mixed record ABI does not support field type '{ft.name}'")
            lines.append(f"    %record_type_{tag}_{fi} = arith.constant {typ} : i64")
            lines.append(f"    %record_type_i_{tag}_{fi} = arith.constant {fi} : index")
            lines.append(f"    memref.store %record_type_{tag}_{fi}, {types_buf}[%record_type_i_{tag}_{fi}] : memref<{max(len(fields),1)}xi64>")
        for ri,row in enumerate(rows):
            for fi,(_,ft) in enumerate(fields):
                arg=row.args[fi]; idx=ri*len(fields)+fi
                if ft.name=="Number":
                    value=_literal_number(arg)
                    if value is None: raise ValueError(f"MLIR mixed record ABI requires literal Number field '{binding.name}'")
                    bits=_f64_bits(value)
                    lines.append(f"    %record_val_{tag}_{ri}_{fi} = arith.constant {bits} : i64")
                elif ft.name=="Boolean":
                    if not hasattr(arg,"value") or not isinstance(arg.value,bool): raise ValueError(f"MLIR mixed record ABI requires literal Boolean field '{binding.name}'")
                    lines.append(f"    %record_val_{tag}_{ri}_{fi} = arith.constant {1 if arg.value else 0} : i64")
                else:
                    if not hasattr(arg,"value") or not isinstance(arg.value,str): raise ValueError(f"MLIR mixed record ABI requires literal Text field '{binding.name}'")
                    encoded=arg.value.encode("utf-8"); size=max(len(encoded)+1,1); sb=f"%record_text_{tag}_{ri}_{fi}"
                    lines.append(f"    {sb} = memref.alloca() : memref<{size}xi8>")
                    for j,b in enumerate(encoded+b"\x00"):
                        lines.append(f"    %record_text_c_{tag}_{ri}_{fi}_{j} = arith.constant {b} : i8")
                        lines.append(f"    %record_text_i_{tag}_{ri}_{fi}_{j} = arith.constant {j} : index")
                        lines.append(f"    memref.store %record_text_c_{tag}_{ri}_{fi}_{j}, {sb}[%record_text_i_{tag}_{ri}_{fi}_{j}] : memref<{size}xi8>")
                    sidx=f"%record_text_pidx_{tag}_{ri}_{fi}"; sptr=f"%record_text_ptr_{tag}_{ri}_{fi}"
                    lines.append(f"    {sidx} = memref.extract_aligned_pointer_as_index {sb}[] : memref<{size}xi8>")
                    lines.append(f"    {sptr} = arith.index_cast {sidx} : index to i64")
                    lines.append(f"    %record_val_{tag}_{ri}_{fi} = arith.constant 0 : i64")
                    lines.append(f"    %record_text_store_i_{tag}_{ri}_{fi} = arith.constant {idx} : index")
                    lines.append(f"    memref.store {sptr}, {text_buf}[%record_text_store_i_{tag}_{ri}_{fi}] : memref<{max(total,1)}xi64>")
                    continue
                lines.append(f"    %record_val_i_{tag}_{ri}_{fi} = arith.constant {idx} : index")
                lines.append(f"    memref.store %record_val_{tag}_{ri}_{fi}, {vals_buf}[%record_val_i_{tag}_{ri}_{fi}] : memref<{max(total,1)}xi64>")
        types_idx=f"%record_types_idx_{tag}"; types_ptr=f"%record_types_ptr_{tag}"; vals_idx=f"%record_values_idx_{tag}"; vals_ptr=f"%record_values_ptr_{tag}"; text_idx=f"%record_texts_idx_{tag}"; text_ptr=f"%record_texts_ptr_{tag}"
        lines.append(f"    {types_idx} = memref.extract_aligned_pointer_as_index {types_buf}[] : memref<{max(len(fields),1)}xi64>")
        lines.append(f"    {types_ptr} = arith.index_cast {types_idx} : index to i64")
        lines.append(f"    {vals_idx} = memref.extract_aligned_pointer_as_index {vals_buf}[] : memref<{max(total,1)}xi64>")
        lines.append(f"    {vals_ptr} = arith.index_cast {vals_idx} : index to i64")
        lines.append(f"    {text_idx} = memref.extract_aligned_pointer_as_index {text_buf}[] : memref<{max(total,1)}xi64>")
        lines.append(f"    {text_ptr} = arith.index_cast {text_idx} : index to i64")
        handle=f"%record_{tag}"
        lines.append(f"    {handle} = func.call @slang_record_mixed_new_flat({types_ptr}, {vals_ptr}, {text_ptr}, {len(fields)}, {len(rows)}) : (i64, i64, i64, i64, i64) -> i64")
        value_by_binding[binding.name]=handle; concrete_bindings=set(value_by_binding)

    # Materialize literal numeric datasets through the concrete collection ABI.
    for ds in getattr(module, "datasets", ()):
        values = _literal_f64_rows(module, ds.name)
        if values is None:
            continue
        elems = ", ".join(f"{v:g}" for v in values)
        lines.append(f"    // literal f64 collection: {ds.name} = [{elems}]")
        if values:
            lines.append(f"    %data_{len(value_by_binding)}_ptr = arith.constant 0 : i64")
            lines.append(f"    %data_{len(value_by_binding)} = func.call @slang_collection_f64_new(%data_{len(value_by_binding)}_ptr, {len(values)}) : (i64, i64) -> i64")
        else:
            lines.append(f"    %data_{len(value_by_binding)} = func.call @slang_collection_f64_new(%zero, 0) : (i64, i64) -> i64")
        value_by_binding[ds.name] = f"%data_{len(value_by_binding)}"
    emitted_regions = set()
    concrete_bindings = set(value_by_binding)
    closed_regions = set()

    # 1.10.48: backend emission must follow the actual dependency graph.
    # ExecutionIR may retain a stable analysis order that is not topological
    # (for example, a filter can be listed before the map that produces its
    # source).  Concrete runtime ABI lowering cannot consume a handle that has
    # not been emitted yet, so use a deterministic stable topological order
    # here without changing semantic node identities or strategy selection.
    original_index = {node.binding: i for i, node in enumerate(ir.nodes)}
    pending = list(ir.nodes)
    ordered_nodes = []
    emitted_bindings = set(value_by_binding)
    while pending:
        ready = [
            node for node in pending
            if all(dep in emitted_bindings or dep not in original_index for dep in node.dependencies)
        ]
        if not ready:
            # A cycle should already have been rejected by semantic analysis.
            # Preserve a deterministic fallback instead of silently dropping a node.
            ready = [min(pending, key=lambda n: original_index[n.binding])]
        ready.sort(key=lambda n: original_index[n.binding])
        for node in ready:
            pending.remove(node)
            ordered_nodes.append(node)
            emitted_bindings.add(node.binding)

    region_node_order = {}
    for node in ordered_nodes:
        region = region_by_node.get(node.binding)
        if region is not None:
            region_node_order.setdefault(region.index, []).append(node.binding)

    for index, node in enumerate(ordered_nodes):
        if node.result in record_fused_intermediates and node.result not in record_fused_final:
            continue
        op = _op_for_node(node)
        if op is None:
            continue
        region = region_by_node.get(node.binding)
        lowering_node = node
        if node.result in record_fused_final:
            synthetic = record_fused_final[node.result]
            class _LowerNode: pass
            lowering_node = _LowerNode()
            lowering_node.__dict__.update(node.__dict__)
            lowering_node.dependencies = (synthetic.source,)
            lowering_node.result = synthetic.result
            source_schema = schema_by_result.get(synthetic.source, (None, None))[1]
            lowering_node.input_schema = source_schema
            lowering_node.output_schema = schema_contract.get(node.binding, (None, None))[1]
            ast_by_result[node.result] = synthetic
        if region is not None and region.index not in emitted_regions:
            emitted_regions.add(region.index)
            nodes = ",".join(region_node_order.get(region.index, region.nodes))
            lines.append(f'    slang.execution_region {{index = {region.index} : i64, mode = "{_esc(region.mode)}", nodes = "{_esc(nodes)}"}}')
            lines.extend(_region_lowering_prefix(region.mode, region.index))

        result_name = f"%v{index}"
        source_override = None
        field_plan = field_strategy_by_consumer.get(node.binding) or field_strategy_by_consumer.get(node.result)
        if field_plan:
            projected = [row for row in field_plan if row[1] == "projected"]
            recompute_rows = [row for row in field_plan if row[1] in {"recompute", "partial-recompute"}]
            unsupported = [row for row in field_plan if row[1] not in {"full", "projected", "recompute", "partial-recompute"}]
            source_binding = getattr(ast_by_result.get(node.result), "source", None)
            source_schema = schema_by_result.get(source_binding, (None, None))[1] if source_binding else getattr(lowering_node, "input_schema", None)
            mixed_source = source_schema is not None and any(getattr(f, "type_name", None) != "Number" for f in getattr(source_schema, "fields", ()))
            # 1.10.73: partial-recompute now has an explicit execution boundary.
            # Reconstruct the producer Record from only the root fields named by
            # the selected provenance detail, then let the current consumer use
            # that reconstructed Record. This is conservative: the optimization
            # is emitted only for same-shape mixed Record maps whose source fields
            # are directly available on the producer input schema.
            if recompute_rows and source_binding and source_binding in ast_by_result:
                producer_op = ast_by_result.get(source_binding)
                producer_source = getattr(producer_op, "source", None)
                producer_input_schema = schema_by_result.get(source_binding, (None, None))[0] if source_binding else None
                producer_output_schema = schema_by_result.get(source_binding, (None, None))[1] if source_binding else None
                producer_expr = getattr(producer_op, "expr", None)
                producer_args = tuple(getattr(producer_expr, "args", ()) or ())
                out_fields = tuple(getattr(producer_output_schema, "fields", ()) or ())
                in_fields = tuple(getattr(producer_input_schema, "fields", ()) or ())
                same_shape = (len(out_fields) == len(in_fields) and
                              len(out_fields) > 0 and
                              tuple((f.name, f.type_name) for f in out_fields) == tuple((f.name, f.type_name) for f in in_fields))
                wanted_targets = {str(row[0]) for row in recompute_rows}
                source_names = set()
                for row in recompute_rows:
                    if len(row) >= 4:
                        source_names.update(str(x) for x in (row[3] or ()))
                source_indices = [i for i, f in enumerate(in_fields) if f.name in source_names]
                # 1.10.74: if provenance roots lie behind multiple Record maps,
                # rebuild the whole same-shape producer chain from the minimal root
                # field set instead of falling back merely because the immediate
                # producer schema does not contain the root names.
                chain_emitted = False
                if same_shape and producer_expr is not None and recompute_rows:
                    # 1.10.75: retain the union of recomputation roots and
                    # direct/projected fields required by the same consumer.
                    retained_root_names = set(source_names)
                    retained_root_names.update(
                        str(row[0]) for row in field_plan
                        if row[1] in {"full", "projected"}
                    )
                    first_target = next((f for f in out_fields if f.name in wanted_targets), None)
                    if first_target is not None:
                        try:
                            fi = next(i for i, f in enumerate(out_fields) if f.name == first_target.name)
                            resolved_expr, root_result, root_schema = _resolve_record_expr_to_root(
                                producer_args[fi] if fi < len(producer_args) else None,
                                source_binding, ast_by_result, schema_by_result
                            )
                        except (StopIteration, TypeError):
                            resolved_expr, root_result, root_schema = None, None, None
                        if root_result is not None and root_result != source_binding:
                            chain_result = _emit_record_recompute_chain(
                                root_result, source_binding, ast_by_result, schema_by_result,
                                value_by_binding, retained_root_names, result_name + "_transitive_recompute"
                            )
                            if chain_result is not None:
                                chain_lines, chain_value = chain_result
                                lines.extend(chain_lines)
                                source_override = chain_value
                                chain_emitted = True
                target_exprs = []
                if same_shape and len(producer_args) == len(out_fields) and source_indices and source_binding in value_by_binding:
                    for fi, f in enumerate(out_fields):
                        if f.name in wanted_targets:
                            target_exprs.append((fi, producer_args[fi]))
                    if target_exprs and all(_record_field_expr_spec(e, producer_input_schema) is not None or _record_mixed_program(e, producer_input_schema, []) is not None for _, e in target_exprs):
                        # For partial-recompute, only provenance dependencies are
                        # retained. Full/recompute fields remain available as well.
                        retained_names = {str(row[2]) for row in field_plan if row[1] in {"full", "projected"}}
                        if any(row[1] == "recompute" for row in recompute_rows):
                            retained_names.update(str(row[0]) for row in recompute_rows)
                        retained_indices = [i for i, f in enumerate(in_fields) if f.name in (source_names | retained_names)]
                        mask_needed = len(retained_indices) < len(in_fields)
                        current_source = None if chain_emitted else (value_by_binding[producer_source] if producer_source in value_by_binding else None)
                        if current_source is not None and mask_needed:
                            ibuf = f"{result_name}_recompute_fields"
                            lines_mask = [f"    {ibuf} = memref.alloca() : memref<{len(retained_indices)}xi64>"]
                            for i, fi in enumerate(retained_indices):
                                lines_mask.append(f"    %recomp_c_{index}_{i} = arith.constant {fi} : i64")
                                lines_mask.append(f"    %recomp_i_{index}_{i} = arith.constant {i} : index")
                                lines_mask.append(f"    memref.store %recomp_c_{index}_{i}, {ibuf}[%recomp_i_{index}_{i}] : memref<{len(retained_indices)}xi64>")
                            ridx=f"{result_name}_recompute_fields_idx"; rptr=f"{result_name}_recompute_fields_ptr"
                            lines_mask.append(f"    {ridx} = memref.extract_aligned_pointer_as_index {ibuf}[] : memref<{len(retained_indices)}xi64>")
                            lines_mask.append(f"    {rptr} = arith.index_cast {ridx} : index to i64")
                            masked_source=f"{result_name}_recompute_source_masked"
                            producer_mixed = any(getattr(f, "type_name", None) != "Number" for f in in_fields)
                            mask_callee = "slang_record_mixed_mask_fields" if producer_mixed else "slang_record_f64_mask_fields"
                            lines_mask.append(f"    {masked_source} = func.call @{mask_callee}({current_source}, {rptr}, {len(retained_indices)}) : (i64, i64, i64) -> i64")
                            lines.extend(lines_mask)
                            current_source = masked_source
                        if current_source is not None:
                            producer_mixed = any(getattr(f, "type_name", None) != "Number" for f in in_fields)
                            if producer_mixed:
                                emitted = _emit_record_mixed_multi_map_program(target_exprs, producer_input_schema, result_name + "_recompute")
                            else:
                                emitted_num = _emit_record_multi_map_program(target_exprs, producer_input_schema, result_name + "_recompute")
                                emitted = (emitted_num[0], emitted_num[1], emitted_num[2], None, 0) if emitted_num else None
                            if emitted:
                                plines, pptr, plen, tptr, tcount = emitted
                                source_override = f"{result_name}_recomputed"
                                lines.extend(plines)
                                if producer_mixed:
                                    lines.append(f"    {source_override} = func.call @slang_record_mixed_map_fields_expr({current_source}, {pptr}, {plen}, {tptr}, {tcount}) : (i64, i64, i64, i64, i64)")
                                else:
                                    lines.append(f"    {source_override} = func.call @slang_record_f64_map_fields_expr({current_source}, {pptr}, {plen}) : (i64, i64, i64) -> i64")
            if projected and not unsupported and mixed_source and source_binding in value_by_binding and source_schema is not None:
                indices = []
                for _, _, _, _ in projected:
                    pass
                wanted = {row[0] for row in projected}
                # Include full fields as well; a mixed full/projected plan must
                # preserve every field explicitly retained by the selected plan.
                wanted.update(row[0] for row in field_plan if row[1] == "full")
                for f in getattr(source_schema, "fields", ()):
                    if f.name in wanted:
                        indices.append(next(i for i, sf in enumerate(getattr(source_schema, "fields", ())) if sf.name == f.name))
                if indices and len(indices) < len(getattr(source_schema, "fields", ())):
                    ibuf = f"{result_name}_selected_fields"
                    lines_mask = [f"    {ibuf} = memref.alloca() : memref<{len(indices)}xi64>"]
                    for i, fi in enumerate(indices):
                        lines_mask.append(f"    %mask_c_{index}_{i} = arith.constant {fi} : i64")
                        lines_mask.append(f"    %mask_i_{index}_{i} = arith.constant {i} : index")
                        lines_mask.append(f"    memref.store %mask_c_{index}_{i}, {ibuf}[%mask_i_{index}_{i}] : memref<{len(indices)}xi64>")
                    midx=f"{result_name}_selected_fields_idx"; mptr=f"{result_name}_selected_fields_ptr"
                    lines_mask.append(f"    {midx} = memref.extract_aligned_pointer_as_index {ibuf}[] : memref<{len(indices)}xi64>")
                    lines_mask.append(f"    {mptr} = arith.index_cast {midx} : index to i64")
                    base_source = source_override or value_by_binding[source_binding]
                    source_override=f"{result_name}_field_masked"
                    lines_mask.append(f"    {source_override} = func.call @slang_record_mixed_mask_fields({base_source}, {mptr}, {len(indices)}) : (i64, i64, i64) -> i64")
                    lines.extend(lines_mask)
        lowered = _runtime_collection_call(lowering_node, result_name, value_by_binding, module, ast_by_result, concrete_bindings, source_override=source_override) or _runtime_call(lowering_node, result_name, value_by_binding)
        if lowered is not None:
            attrs = [f'node = "{_esc(node.binding)}"', f'kind = "{_esc(node.kind)}"']
            in_type, out_type = type_contract.get(node.binding, (None, None))
            in_schema, out_schema = schema_contract.get(node.binding, (None, None))
            if in_type is not None:
                attrs.append(f'input_type = "{_esc(in_type)}"')
            if out_type is not None:
                attrs.append(f'output_type = "{_esc(out_type)}"')
            for label, schema in (("input_schema", in_schema), ("output_schema", out_schema)):
                if schema is not None:
                    fields = ",".join(f"{f.name}:{f.type_name}" for f in schema.fields)
                    attrs.append(f'{label} = "{_esc(schema.name)}[{fields}]"')
                    role = "input" if label == "input_schema" else "output"
                    mapped = []
                    for field in schema.fields:
                        sid = storage_ids.get((node.binding, role, field.name))
                        if sid is not None:
                            mapped.append(f"{field.name}->{sid}")
                    if mapped:
                        attrs.append(f'{label}_storage = "{_esc(";".join(mapped))}"')
            if region is not None:
                attrs.append(f'execution_mode = "{_esc(region.mode)}"')
            field_plan = field_strategy_by_consumer.get(node.binding) or field_strategy_by_consumer.get(node.result)
            fanout_req = fanout_fields_by_endpoint.get(str(node.result))
            if fanout_req:
                attrs.append(f'record_fanout_fields = "{_esc(",".join(fanout_req))}"')
            shared_req = shared_recompute_by_endpoint.get(str(node.result))
            if shared_req:
                attrs.append(f'record_shared_recompute = "{_esc(";".join(f"{field}:{shared_cost:g}" for field, _src, _independent, shared_cost in shared_req))}"')
            if field_plan:
                encoded = ";".join(
                    f"{field}:{strategy}:{cost:g}:" + (",".join(source_fields) or "-")
                    for field, strategy, cost, source_fields in sorted(field_plan)
                )
                attrs.append(f'record_field_plan = "{_esc(encoded)}"')
            if region is not None:
                attrs.append(f'execution_region = {region.index} : i64')
            if node.cardinality is not None:
                attrs.append(f'cardinality = {node.cardinality} : i64')
            if node.data_shape is not None:
                attrs.append(f'complexity = "{_esc(node.data_shape.complexity)}"')
            # Keep compiler provenance on a standard MLIR comment rather than
            # attaching unsupported arbitrary attributes to func.call.
            lines.append(f"      // S-Lang node: {', '.join(attrs)}")
            lines.append(("      " if region is not None else "    ") + lowered)
            value_by_binding[node.binding] = result_name
            value_by_binding[node.result] = result_name
            if node.result in record_boundaries and node.kind in {"filter", "map"}:
                mixed_boundary = any(getattr(f, "type_name", None) != "Number" for f in (getattr(schema_contract.get(node.binding, (None, None))[1], "fields", ()) or ()))
                mat_name = result_name + "_materialized"
                shared_boundary = str(node.result) in shared_recompute_by_endpoint
                if shared_boundary:
                    callee = "slang_record_mixed_share" if mixed_boundary else "slang_record_f64_share"
                    lines.append(f"      // selected shared Record endpoint: {node.result}; reuse one physical handle")
                else:
                    callee = "slang_record_mixed_materialize" if mixed_boundary else "slang_record_f64_materialize"
                    lines.append(f"      // selected Record materialization boundary: {node.result}")
                lines.append(f"      {mat_name} = func.call @{callee}({result_name}) : (i64) -> i64")
                # Global fan-out retention contract: the shared boundary keeps
                # the union of fields required by every downstream consumer.
                # Individual consumers may still project/recompute from this
                # shared value without changing the value seen by sibling
                # consumers.
                retained_names = fanout_fields_by_endpoint.get(str(node.result))
                boundary_schema = schema_contract.get(node.binding, (None, None))[1]
                boundary_fields = tuple(getattr(boundary_schema, "fields", ()) or ())
                if retained_names and boundary_fields and len(retained_names) < len(boundary_fields):
                    retained_indices = [i for i, field in enumerate(boundary_fields)
                                        if str(getattr(field, "name", "")) in set(retained_names)]
                    if retained_indices:
                        fbuf = f"{result_name}_fanout_fields"
                        lines_mask = [f"      {fbuf} = memref.alloca() : memref<{len(retained_indices)}xi64>"]
                        for fi_pos, field_index in enumerate(retained_indices):
                            lines_mask.append(f"      %fanout_c_{index}_{fi_pos} = arith.constant {field_index} : i64")
                            lines_mask.append(f"      %fanout_i_{index}_{fi_pos} = arith.constant {fi_pos} : index")
                            lines_mask.append(f"      memref.store %fanout_c_{index}_{fi_pos}, {fbuf}[%fanout_i_{index}_{fi_pos}] : memref<{len(retained_indices)}xi64>")
                        fidx = f"{result_name}_fanout_fields_idx"
                        fptr = f"{result_name}_fanout_fields_ptr"
                        lines_mask.append(f"      {fidx} = memref.extract_aligned_pointer_as_index {fbuf}[] : memref<{len(retained_indices)}xi64>")
                        lines_mask.append(f"      {fptr} = arith.index_cast {fidx} : index to i64")
                        masked = f"{result_name}_fanout_retained"
                        mixed_boundary = any(getattr(field, "type_name", None) != "Number" for field in boundary_fields)
                        mask_callee = "slang_record_mixed_mask_fields" if mixed_boundary else "slang_record_f64_mask_fields"
                        lines_mask.append(f"      {masked} = func.call @{mask_callee}({mat_name}, {fptr}, {len(retained_indices)}) : (i64, i64, i64) -> i64")
                        lines.extend(lines_mask)
                        mat_name = masked
                value_by_binding[node.binding] = mat_name
                value_by_binding[node.result] = mat_name
            if node.kind in {"filter", "map", "sort"} and (
                (getattr(ast_by_result.get(node.result), "source", None) in concrete_bindings)
                or (node.dependencies and node.dependencies[0] in concrete_bindings)
                or "@slang_record_" in lowered
            ):
                # The AST source binding is authoritative for collection pipelines.
                # Some ExecutionIR nodes also carry type-level dependencies (for
                # example @fn:Summary) before the actual data dependency, so using
                # dependencies[0] alone would incorrectly break a concrete Record chain.
                concrete_bindings.add(node.binding)
        else:
            attrs = [f'node = "{_esc(node.binding)}"', f'kind = "{_esc(node.kind)}"']
            in_type, out_type = type_contract.get(node.binding, (None, None))
            in_schema, out_schema = schema_contract.get(node.binding, (None, None))
            if in_type is not None:
                attrs.append(f'input_type = "{_esc(in_type)}"')
            if out_type is not None:
                attrs.append(f'output_type = "{_esc(out_type)}"')
            if region is not None:
                attrs.append(f'execution_mode = "{_esc(region.mode)}"')
                attrs.append(f'execution_region = {region.index} : i64')
            if node.cardinality is not None:
                attrs.append(f'cardinality = {node.cardinality} : i64')
            if node.data_shape is not None:
                attrs.append(f'complexity = "{_esc(node.data_shape.complexity)}"')
            indent = '      ' if region is not None else '    '
            lines.append(f'{indent}{result_name} = {op} {{{", ".join(attrs)}}} : i64')
            value_by_binding[node.binding] = result_name

        if region is not None and node.binding == (region.nodes[-1] if region.nodes else None) and region.index not in closed_regions:
            lines.extend(_region_lowering_suffix(region.mode, region.index))
            closed_regions.add(region.index)
    lines.append("    return %zero : i64")
    lines.extend(["  }", "}"])
    return "\n".join(lines)


def format_backend_lowering(module) -> str:
    pipeline = compile_semantic_pipeline(module)
    domains = []
    for node in pipeline.optimized_ir.nodes:
        if node.kind not in domains:
            domains.append(node.kind)
    return "\n".join([
        "backend.mlir.lowering {",
        "  source = ExecutionIR",
        f"  optimized_nodes = {len(pipeline.optimized_ir.nodes)}",
        "  semantic_operations = " + (", ".join(domains) if domains else "none"),
        "  representation = slang-runtime-abi-mlir",
        "  runtime_abi = explicit-i64-handles",
        "  llvm_executable = runtime-abi-entry-points-required",
        "  deterministic = yes",
        "}",
    ])


def lower_compiler_artifact_to_mlir(artifact) -> str:
    """Lower a persisted ``CompilerArtifact`` into concrete MLIR operations.

    This path consumes only the persisted optimized ExecutionIR and selected
    execution plan.  Each supported semantic node is lowered to an explicit
    runtime-ABI ``func.call``; the selected execution region/segment remains
    visible as deterministic structural metadata.  No source parsing or
    semantic re-analysis is performed.
    """
    from .compiler_artifact import CompilerArtifact
    if not isinstance(artifact, CompilerArtifact):
        raise TypeError("lower_compiler_artifact_to_mlir expects CompilerArtifact")
    if artifact.artifact_version != "7":
        raise ValueError("unsupported compiler artifact version for MLIR lowering")
    nodes = artifact.optimized_ir.get("nodes", ())
    if not isinstance(nodes, list):
        raise ValueError("invalid optimized_ir in compiler artifact")
    strategy_by_node = dict(artifact.strategy_contract)
    operation_by_binding = {binding: (kind, params) for binding, kind, params in artifact.operation_contract}
    materialization_by_binding = {binding: (kind, canonical, seed) for binding, kind, canonical, seed in artifact.parameter_materialization}
    descriptor_by_binding = {binding: (kind, value_type, byte_size, fmt, encoding) for binding, kind, value_type, byte_size, fmt, encoding in artifact.parameter_abi_descriptors}
    from .runtime_parameter_abi import build_runtime_parameter_table
    runtime_parameter_table = build_runtime_parameter_table(artifact)
    selected = artifact.selected_execution_plan or {}
    if not selected or selected.get("schema") != "slang-selected-execution-plan-1":
        raise ValueError("compiler artifact has no selected execution plan")

    region_by_node = {}
    for region in selected.get("execution_regions", []):
        if not isinstance(region, dict):
            raise ValueError("invalid execution region in compiler artifact")
        for node_name in region.get("nodes", []):
            region_by_node[str(node_name)] = region
    segment_by_node = {}
    for segment in selected.get("segments", []):
        if not isinstance(segment, dict):
            raise ValueError("invalid execution segment in compiler artifact")
        for node_name in segment.get("nodes", []):
            segment_by_node[str(node_name)] = segment

    runtime_abi = {
        "filter": "slang_filter",
        "map": "slang_map",
        "sort": "slang_sort",
        "aggregate": "slang_aggregate",
        "reduce": "slang_reduce",
        "sequence": "slang_sequence",
        "goal:select": "slang_choose",
        "goal:path": "slang_find_path",
        "goal:satisfy": "slang_satisfy",
        "physics.gravity": "slang_simulate_gravity",
        "effect:show": "slang_show",
    }
    declarations = [
        "  func.func private @slang_artifact_param(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_materialize_param(%seed: i64) -> i64",
        "  func.func private @slang_filter(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_map(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_sort(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_aggregate(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_reduce(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_sequence(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_choose(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_find_path(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_satisfy(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_simulate_gravity(%src: i64, %param: i64) -> i64",
        "  func.func private @slang_show(%src: i64) -> i64",
    ]
    lines = [
        "module {",
        f'  // slang.compiler_artifact = "{artifact.fingerprint}"',
        *declarations,
        '  func.func @main() -> i64 {',
        '    %zero = arith.constant 0 : i64',
    ]
    value_by_binding = {}
    for index, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise ValueError("invalid ExecutionIR node in compiler artifact")
        binding = str(node.get("binding", ""))
        kind = str(node.get("kind", "generic"))
        strategy = str(strategy_by_node.get(binding, "generic"))
        region = region_by_node.get(binding, {})
        segment = segment_by_node.get(binding, {})
        region_index = region.get("index", "none")
        region_mode = region.get("mode", "none")
        segment_index = segment.get("index", "none")
        segment_mode = segment.get("mode", "none")
        lines.append(
            f'    // artifact-node {index}: binding="{binding}" kind="{kind}" strategy="{strategy}"'
        )
        lines.append(
            f'    // selected-region={region_index} mode={region_mode} segment={segment_index} segment_mode={segment_mode}'
        )
        if binding in value_by_binding:
            source = value_by_binding[binding]
        else:
            deps = node.get("dependencies", [])
            source = value_by_binding.get(str(deps[0]), "%zero") if deps else "%zero"
        callee = runtime_abi.get(kind)
        result = f"%artifact_{index}"
        operation = operation_by_binding.get(binding)
        if operation is None and "#" in binding:
            operation = operation_by_binding.get(binding.split("#", 1)[0])
        materialized = materialization_by_binding.get(binding)
        if materialized is None and "#" in binding:
            materialized = materialization_by_binding.get(binding.split("#", 1)[0])
        if materialized is not None:
            _, canonical, seed = materialized
            descriptor = descriptor_by_binding.get(binding) or descriptor_by_binding.get(binding.split("#", 1)[0])
            if descriptor is None:
                raise ValueError(f"missing parameter ABI descriptor for {binding}")
            _, value_type, byte_size, fmt, encoding = descriptor
            runtime_descriptor = runtime_parameter_table.get(binding) or runtime_parameter_table.get(binding.split("#", 1)[0])
            if runtime_descriptor is None or runtime_descriptor.seed != int(seed):
                raise ValueError(f"runtime parameter descriptor mismatch for {binding}")
            lines.append(f"    // runtime-parameter-descriptor binding={runtime_descriptor.binding} kind={runtime_descriptor.kind} type={runtime_descriptor.value_type} bytes={runtime_descriptor.byte_size} format={runtime_descriptor.format} encoding={runtime_descriptor.encoding} seed={runtime_descriptor.seed}")
            lines.append(f"    // parameter-abi type={value_type} bytes={byte_size} format={fmt} encoding={encoding}")
            lines.append(f"    %param_seed_{index} = arith.constant {seed} : i64")
            lines.append(f"    %param_{index} = func.call @slang_materialize_param(%param_seed_{index}) : (i64) -> i64")
            lines.append(f'    // operation-parameter-materialized seed={seed} payload={_esc(canonical)}')
        else:
            lines.append(f"    %param_{index} = arith.constant 0 : i64")
        if callee is None:
            # Unknown semantic nodes remain explicit rather than silently
            # disappearing; the operation is still concrete and deterministic.
            lines.append(
                f'    "slang.artifact.unsupported"() {{binding = "{_esc(binding)}", kind = "{_esc(kind)}", strategy = "{_esc(strategy)}"}} : () -> ()'
            )
            value_by_binding[binding] = source
            continue
        if kind == "effect:show":
            lines.append(f'    {result} = func.call @{callee}({source}) : (i64) -> i64')
        else:
            lines.append(f'    {result} = func.call @{callee}({source}, %param_{index}) : (i64, i64) -> i64')
        value_by_binding[binding] = result

    final_value = next(reversed(value_by_binding.values()), "%zero") if value_by_binding else "%zero"
    lines += [
        f'    return {final_value} : i64',
        '  }',
        '}',
    ]
    return "\n".join(lines)
