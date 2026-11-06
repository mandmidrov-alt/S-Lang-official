"""Plan-aware runtime boundary for S-Lang 1.8.x.

The runtime keeps the existing reference interpreter as a verified fallback,
while progressively executing selected plans directly, including mixed-domain
programs through the unified 1.8 runtime executor. The reference interpreter is
isolated behind ``reference_runtime`` and is only entered for unsupported plans.
This is the first 1.8 step: planning is no longer merely diagnostic metadata;
the runtime validates the plan before dispatching execution and records a
stable, backend-neutral execution trace.
"""
from __future__ import annotations
from dataclasses import dataclass
from .compiler_pipeline import compile_semantic_pipeline
from .plan_runtime_support import FunctionValue


@dataclass(frozen=True)
class RuntimeStep:
    level: int
    node: str
    strategy: str
    status: str


@dataclass(frozen=True)
class RuntimeTrace:
    steps: tuple[RuntimeStep, ...]
    deterministic: bool = True
    executor: str = "reference-interpreter"

    @property
    def completed(self) -> int:
        return sum(1 for step in self.steps if step.status == "completed")

    @property
    def operation_count(self) -> int:
        return len(self.steps)


def validate_runtime_plan(pipeline) -> None:
    """Verify that the selected plan is complete before runtime dispatch."""
    from .determinism import validate_segment_determinism
    validate_segment_determinism(pipeline.selected_execution_plan, ir=pipeline.optimized_ir)
    expected = [node for step in pipeline.execution_plan.steps for node in step.nodes]
    selected = [step.node for step in pipeline.selected_execution_plan.steps]
    if expected != selected:
        raise ValueError("selected execution plan does not cover semantic execution plan")
    if len(set(selected)) != len(selected):
        raise ValueError("selected execution plan contains duplicate nodes")
    if any(step.strategy == "" for step in pipeline.selected_execution_plan.steps):
        raise ValueError("selected execution plan contains an empty strategy")


def build_runtime_trace(pipeline, status: str = "completed", executor: str = "reference-interpreter") -> RuntimeTrace:
    validate_runtime_plan(pipeline)
    return RuntimeTrace(
        tuple(RuntimeStep(step.level, step.node, step.strategy, status) for step in pipeline.selected_execution_plan.steps),
        deterministic=pipeline.selected_execution_plan.deterministic,
        executor=executor,
    )


def _binding_name(node: str) -> str:
    return node.rsplit("#", 1)[0]


class _PlanReturnSignal:
    def __init__(self, value):
        self.value = value


class _PlanFunctionValue(FunctionValue):
    """Function value whose body is evaluated by the plan runtime.

    Expression semantics are still delegated to the verified expression
    evaluator, but function control flow (let/if/return and nested functions)
    is executed here rather than through ``core._eval_block``.
    """
    def __init__(self, decl, program, closure=None, evaluator=None):
        super().__init__(decl, program, closure=closure)
        self._evaluator = evaluator

    @property
    def name(self):
        return self.decl.name

    def __call__(self, args):
        if len(args) != len(self.decl.parameters):
            raise TypeError(
                f"function '{self.decl.name}' expects {len(self.decl.parameters)} argument(s), got {len(args)}"
            )
        local = dict(self.closure or {})
        local.update({name: value for (name, _), value in zip(self.decl.parameters, args)})
        signal = self._evaluator(self.decl.body, local=local)
        if isinstance(signal, _PlanReturnSignal):
            return signal.value
        raise TypeError("block completed without return")


def _can_plan_bindings(module, pipeline) -> bool:
    names = {binding.name for binding in module.ast.bindings}
    planned = {_binding_name(step.node) for step in pipeline.selected_execution_plan.steps
               if not pipeline.optimized_ir.by_binding()[step.node].kind.startswith("effect:")}
    return bool(names) and names == planned and not module.ast.states and not module.ast.state_sets


def _collection_operations(module):
    return {
        "filter": {op.result: op for op in module.ast.filters},
        "sort": {op.result: op for op in module.ast.sorts},
        "map": {op.result: op for op in module.ast.maps},
        "aggregate": {op.result: op for op in module.ast.aggregates},
        "reduce": {op.result: op for op in module.ast.reduces},
        "conditional-pipeline": {op.result: op for op in module.ast.conditional_pipelines},
    }


def _can_plan_collections(module, pipeline) -> bool:
    if module.ast.states or module.ast.state_sets or module.ast.sequences:
        return False
    if module.ast.goals or module.ast.path_goals or module.ast.satisfy_goals:
        return False
    if not any((module.ast.filters, module.ast.sorts, module.ast.maps, module.ast.aggregates, module.ast.reduces, module.ast.conditional_pipelines)):
        return False
    by = pipeline.optimized_ir.by_binding()
    allowed = {"filter", "sort", "map", "aggregate", "reduce", "conditional-pipeline", "binding", "effect:show"}
    return all(by[step.node].kind in allowed for step in pipeline.selected_execution_plan.steps)

def _execute_planned_collections(module, pipeline):
    """Execute pure collection dataflow using the selected runtime strategies."""
    from concurrent.futures import ThreadPoolExecutor
    from .plan_expression import eval_expr as _eval_expr, eval_pipeline_expr as _eval_pipeline_expr
    from .plan_runtime_support import qadd, qdiv

    module.entities = {}
    module._bindings = {}
    module._collections = {name: list(rows) for name, rows in (module.data_tables or {}).items()}
    ops = _collection_operations(module)
    ir = pipeline.optimized_ir.by_binding()
    steps = pipeline.selected_execution_plan.steps
    profile = pipeline.execution_profile

    def par_apply(values, fn):
        workers = min(profile.cpu_cores, len(values))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            return list(pool.map(fn, values))

    # Fusion terminal: execute the complete source->filter->map->terminal
    # chain directly, so intermediate collections are not materialized.
    def execute_fused(op, strategy):
        stage_by_result = {}
        stage_by_result.update(ops["filter"])
        stage_by_result.update(ops["map"])
        chain, current = [], op.source
        while current in stage_by_result:
            stage = stage_by_result[current]
            chain.append(stage)
            current = stage.source
        chain.reverse()
        if current not in module._collections:
            return False
        if op.__class__.__name__ == "ReduceOp":
            result = _eval_expr(op.initial, module)
        else:
            projected = []
        for row in module._collections[current]:
            value = row
            keep = True
            for stage in chain:
                if stage.__class__.__name__ == "FilterOp":
                    if not bool(_eval_pipeline_expr(stage.predicate.expr, module, value)):
                        keep = False
                        break
                else:
                    value = _eval_pipeline_expr(stage.expr, module, value)
            if not keep:
                continue
            if op.__class__.__name__ == "ReduceOp":
                result = _eval_expr(op.expr, module, row=value, local={"acc": result})
            else:
                projected.append(_eval_pipeline_expr(op.expr, module, value))
        if op.__class__.__name__ == "ReduceOp":
            module._collections[op.result] = result
        else:
            if op.operation == "count":
                result = len(projected)
            elif not projected:
                raise TypeError(f"aggregate '{op.operation}' cannot operate on an empty collection")
            elif op.operation == "sum":
                result = projected[0]
                for value in projected[1:]:
                    result = qadd(result, value) if hasattr(result, "unit") else result + value
            elif op.operation == "max": result = max(projected)
            elif op.operation == "min": result = min(projected)
            elif op.operation in ("average", "avg"):
                result = projected[0]
                for value in projected[1:]:
                    result = qadd(result, value) if hasattr(result, "unit") else result + value
                result = qdiv(result, len(projected))
            else: raise TypeError(f"unknown aggregate operation '{op.operation}'")
            module._collections[op.result] = result
        return True

    # Fused terminals consume their upstream semantic nodes.
    fused_terminals = {_binding_name(s.node): s for s in steps if s.strategy.startswith("fused-")}
    consumed = set()
    for terminal_result, terminal_step in fused_terminals.items():
        terminal_kind = ir[terminal_step.node].kind
        terminal_op = ops.get(terminal_kind, {}).get(terminal_result)
        if terminal_op is None:
            continue
        current = terminal_op.source
        while current in ops["filter"] or current in ops["map"]:
            consumed.add(current)
            current = (ops["filter"].get(current) or ops["map"].get(current)).source
    for step in steps:
        result = _binding_name(step.node)
        if result in consumed:
            continue
        kind = ir[step.node].kind
        if kind == "effect:show":
            # `show` is rendered after runtime execution; keep its plan ordering
            # without materializing or printing during execution.
            continue
        if kind == "binding":
            binding = next((b for b in module.ast.bindings if b.name == result), None)
            if binding is None:
                raise RuntimeError(f"selected binding '{result}' has no AST declaration")
            value = _eval_expr(binding.expr, module)
            if isinstance(value, list):
                module._collections[result] = value
            else:
                module._bindings[result] = value
            consumed.add(result)
            continue
        op = ops.get(kind, {}).get(result)
        if op is None:
            raise RuntimeError(f"selected plan operation '{result}' has no runtime operation")
        if kind == "conditional-pipeline":
            if step.strategy != "conditional-pipeline":
                raise RuntimeError(f"unsupported conditional pipeline runtime strategy {step.strategy!r}")
            if op.source not in module._collections:
                raise RuntimeError(f"collection source '{op.source}' is not available for '{result}'")
            condition = _eval_expr(op.condition, module)
            if not isinstance(condition, bool):
                raise TypeError("conditional pipeline condition must evaluate to Boolean")
            value = module._collections[op.source]
            stages = op.then_stages if condition else op.else_stages
            for stage_kind, stage_expr in stages:
                if stage_kind == "where":
                    values = value if isinstance(value, list) else [value]
                    value = [row for row in values if bool(_eval_pipeline_expr(stage_expr.expr, module, row))]
                elif stage_kind == "map":
                    values = value if isinstance(value, list) else [value]
                    value = [_eval_pipeline_expr(stage_expr, module, row) for row in values]
                elif stage_kind == "sort":
                    values = value if isinstance(value, list) else [value]
                    value = sorted(values, key=lambda row: _eval_pipeline_expr(stage_expr.expr, module, row), reverse=not stage_expr.ascending)
                elif stage_kind == "aggregate":
                    name, expr = stage_expr
                    values = value if isinstance(value, list) else [value]
                    projected = [_eval_pipeline_expr(expr, module, row) for row in values]
                    if name == "count":
                        value = len(projected)
                    elif not projected:
                        raise TypeError(f"aggregate '{name}' cannot operate on an empty collection")
                    elif name == "sum":
                        total = projected[0]
                        for item in projected[1:]:
                            total = qadd(total, item) if hasattr(total, "unit") else total + item
                        value = total
                    elif name == "max":
                        value = max(projected)
                    elif name == "min":
                        value = min(projected)
                    elif name in ("average", "avg"):
                        total = projected[0]
                        for item in projected[1:]:
                            total = qadd(total, item) if hasattr(total, "unit") else total + item
                        value = qdiv(total, len(projected))
                    else:
                        raise TypeError(f"unknown aggregate operation '{name}'")
                elif stage_kind == "reduce":
                    initial_expr, step_expr = stage_expr
                    values = value if isinstance(value, list) else [value]
                    acc = _eval_expr(initial_expr, module)
                    for item in values:
                        acc = _eval_expr(step_expr, module, row=item, local={"acc": acc})
                    value = acc
                else:
                    raise RuntimeError(f"unknown conditional pipeline operation '{stage_kind}'")
            module._collections[result] = value
            consumed.add(result)
            continue
        if result in fused_terminals:
            if not execute_fused(op, step.strategy):
                raise RuntimeError(f"cannot execute fusion strategy {step.strategy!r} for '{result}'")
            cur = op.source
            while cur in ops["filter"] or cur in ops["map"]:
                consumed.add(cur)
                cur = (ops["filter"].get(cur) or ops["map"].get(cur)).source
            consumed.add(result)
            continue
        source = op.source
        if source not in module._collections:
            raise RuntimeError(f"collection source '{source}' is not available for '{result}'")
        values = module._collections[source]
        strategy = step.strategy
        if kind == "filter":
            if strategy == "scan-filter":
                out = [row for row in values if bool(_eval_pipeline_expr(op.predicate.expr, module, row))]
            elif strategy == "parallel-filter":
                flags = par_apply(values, lambda row: bool(_eval_pipeline_expr(op.predicate.expr, module, row)))
                out = [row for row, keep in zip(values, flags) if keep]
            else: raise RuntimeError(f"unsupported filter runtime strategy {strategy!r}")
        elif kind == "map":
            if strategy == "sequential-map":
                out = [_eval_pipeline_expr(op.expr, module, row) for row in values]
            elif strategy == "parallel-map":
                out = par_apply(values, lambda row: _eval_pipeline_expr(op.expr, module, row))
            else: raise RuntimeError(f"unsupported map runtime strategy {strategy!r}")
        elif kind == "sort":
            if strategy not in {"stable-sort", "parallel-stable-sort"}:
                raise RuntimeError(f"unsupported sort runtime strategy {strategy!r}")
            out = sorted(values, key=lambda row: _eval_pipeline_expr(op.spec.expr, module, row), reverse=not op.spec.ascending)
        elif kind == "aggregate":
            if strategy != "sequential-aggregate": raise RuntimeError(f"unsupported aggregate runtime strategy {strategy!r}")
            vals = [_eval_pipeline_expr(op.expr, module, row) for row in values]
            if op.operation == "count": out = len(vals)
            elif not vals: raise TypeError(f"aggregate '{op.operation}' cannot operate on an empty collection")
            elif op.operation in ("sum", "average", "avg"):
                out = vals[0]
                for value in vals[1:]: out = qadd(out, value) if hasattr(out, "unit") else out + value
                if op.operation in ("average", "avg"): out = qdiv(out, len(vals))
            elif op.operation == "max": out = max(vals)
            elif op.operation == "min": out = min(vals)
            else: raise TypeError(f"unknown aggregate operation '{op.operation}'")
        elif kind == "reduce":
            if strategy != "sequential-reduce": raise RuntimeError(f"unsupported reduce runtime strategy {strategy!r}")
            out = _eval_expr(op.initial, module)
            for item in values: out = _eval_expr(op.expr, module, row=item, local={"acc": out})
        else: raise RuntimeError(f"unsupported collection operation kind '{kind}'")
        module._collections[result] = out
        consumed.add(result)

    results = [f.result for f in module.ast.filters] + [s.result for s in module.ast.sorts] + [m.result for m in module.ast.maps] + [a.result for a in module.ast.aggregates] + [r.result for r in module.ast.reduces]
    if results:
        module._data_result_name = results[-1]
        module._data_result = module._collections[results[-1]]
    return module

def _execute_planned_bindings(module, pipeline):
    """Execute top-level bindings in the selected plan's level order.

    Independent bindings in a parallel execution level are evaluated from the
    same completed snapshot and merged only after all workers finish. This keeps
    the observable result deterministic while making the selected plan an actual
    execution decision rather than trace-only metadata.
    """
    from concurrent.futures import ThreadPoolExecutor
    from .plan_expression import eval_expr as _eval_expr

    module.entities = {}
    module._bindings = {}
    binding_by_name = {binding.name: binding for binding in module.ast.bindings}
    steps_by_level = {}
    for step in pipeline.selected_execution_plan.steps:
        steps_by_level.setdefault(step.level, []).append(step)

    for level in sorted(steps_by_level):
        steps = steps_by_level[level]
        values = {}
        parallel = (
            pipeline.execution_profile.allow_parallelism
            and pipeline.execution_profile.cpu_cores > 1
            and len(steps) > 1
            and all(step.parallelism == "parallel-where-independent" for step in steps)
        )

        executable_steps = [
            step for step in steps
            if pipeline.optimized_ir.by_binding()[step.node].kind != "effect:show"
        ]

        def evaluate(step):
            binding = binding_by_name[_binding_name(step.node)]
            return binding.name, _eval_expr(binding.expr, module)

        parallel = parallel and len(executable_steps) > 1
        if parallel:
            workers = min(pipeline.execution_profile.cpu_cores, len(executable_steps))
            with ThreadPoolExecutor(max_workers=workers) as pool:
                for name, value in pool.map(evaluate, executable_steps):
                    values[name] = value
        else:
            for step in executable_steps:
                name, value = evaluate(step)
                values[name] = value

        for name in sorted(values):
            value = values[name]
            if hasattr(value, "name") and value.__class__.__name__ == "UserEntity":
                value.name = name
                module.entities[name] = value
            else:
                module._bindings[name] = value
    return module




def _can_plan_stateful(module, pipeline) -> bool:
    """Whether the selected plan can execute state declarations and writes directly.

    Stateful execution is intentionally sequential: the selected plan determines
    the legal order, while the runtime preserves every state read/write boundary.
    This avoids treating mutable state as reorderable even when unrelated nodes
    happen to share a dependency level.
    """
    if not (module.ast.states or module.ast.state_sets):
        return False
    if module.ast.simulations:
        return False
    by = pipeline.optimized_ir.by_binding()
    allowed = {"state:init", "state:set", "state:read", "binding", "effect:show"}
    return all(by[step.node].kind in allowed for step in pipeline.selected_execution_plan.steps)


def _execute_planned_stateful(module, pipeline):
    """Execute stateful declarations through the selected execution plan.

    Synthetic ``state:read`` nodes are dependency barriers produced by the IR;
    reading the state itself is performed by the normal expression evaluator.
    State writes execute strictly in selected-plan order.
    """
    from .plan_expression import eval_expr as _eval_expr

    module.entities = {}
    module._bindings = {}
    module._states = {}
    bindings = {b.name: b for b in module.ast.bindings}
    states = {s.name: s for s in module.ast.states}
    state_sets = {}
    for index, op in enumerate(module.ast.state_sets, 1):
        state_sets[f"@state:{op.name}:set:{index}"] = op

    for step in pipeline.selected_execution_plan.steps:
        node = step.node
        ir_kind = pipeline.optimized_ir.by_binding()[node].kind
        if ir_kind == "state:read":
            # The IR node is a dependency/memory boundary, not a separate
            # runtime value. Expressions resolve the state by name.
            continue

        if ir_kind == "effect:show":
            # `show` is an ordered observation effect. The CLI renders it after
            # runtime execution; there is no separate value to materialize here.
            continue

        if ir_kind == "state:init":
            state_name = node.split(":", 2)[1]
            state = states.get(state_name)
            if state is None:
                raise RuntimeError(f"selected state '{state_name}' has no AST declaration")
            if state_name in module._states:
                raise TypeError(f"duplicate state '{state_name}'")
            module._states[state_name] = _eval_expr(state.expr, module)
            continue

        if ir_kind == "state:set":
            base_node = node.rsplit("#", 1)[0]
            op = state_sets.get(base_node)
            if op is None:
                # The IR index is local to state-set operations of the same
                # state, so resolve by the encoded state name and occurrence.
                parts = base_node.split(":")
                state_name = parts[1] if len(parts) > 1 else ""
                occurrence = int(parts[-1]) if parts and parts[-1].isdigit() else 0
                candidates = [x for x in module.ast.state_sets if x.name == state_name]
                op = candidates[occurrence - 1] if 0 < occurrence <= len(candidates) else None
            if op is None:
                raise RuntimeError(f"selected state write '{node}' has no AST declaration")
            if op.name not in module._states:
                raise TypeError(f"unknown state '{op.name}'")
            module._states[op.name] = _eval_expr(op.expr, module)
            continue

        if ir_kind == "binding":
            name = _binding_name(node)
            binding = bindings.get(name)
            if binding is None:
                raise RuntimeError(f"selected binding '{name}' has no AST declaration")
            value = _eval_expr(binding.expr, module)
            if hasattr(value, "name") and value.__class__.__name__ == "UserEntity":
                value.name = name
                module.entities[name] = value
            else:
                module._bindings[name] = value
            continue

        raise RuntimeError(f"unsupported stateful runtime IR kind '{ir_kind}'")
    return module

def _can_plan_specialized_goals(module, pipeline) -> bool:
    """Whether the selected plan can be executed by the goal runtime.

    This executor covers pure goal/transition operations. Stateful declarations,
    conditional pipelines and side-effecting constructs remain on the reference
    interpreter until their dedicated runtime contracts are implemented.
    """
    if module.ast.states or module.ast.state_sets or module.ast.conditional_pipelines:
        return False
    if module.ast.simulations:
        return False
    if not (module.ast.sequences or module.ast.goals or module.ast.path_goals or module.ast.satisfy_goals):
        return False
    by = pipeline.optimized_ir.by_binding()
    allowed = {"binding", "sequence", "goal:transition", "goal:select", "goal:path", "goal:satisfy", "effect:show"}
    return all(by[step.node].kind in allowed for step in pipeline.selected_execution_plan.steps)


def _execute_specialized_goals(module, pipeline):
    """Execute pure goal and transition strategies selected by the compiler."""
    import heapq
    import itertools
    from .plan_expression import eval_expr as _eval_expr
    from .plan_runtime_support import _goal_distance, GraphPath

    module.entities = {}
    module._bindings = {}
    module._collections = {name: list(rows) for name, rows in (module.data_tables or {}).items()}
    for name, value in list(module._bindings.items()):
        if isinstance(value, list):
            module._collections[name] = value

    bindings = {b.name: b for b in module.ast.bindings}
    sequences = {o.result: o for o in module.ast.sequences}
    goals = {o.result: o for o in module.ast.goals}
    paths = {o.result: o for o in module.ast.path_goals}
    satisfies = {o.result: o for o in module.ast.satisfy_goals}
    graphs = {g.name: g for g in module.ast.graphs}

    for step in pipeline.selected_execution_plan.steps:
        result = _binding_name(step.node)
        kind = pipeline.optimized_ir.by_binding()[step.node].kind
        strategy = step.strategy

        if kind == "effect:show":
            # Rendering is performed by the CLI after execution. The selected
            # plan only needs to preserve the observation dependency boundary.
            continue

        if kind == "binding":
            binding = bindings.get(result)
            if binding is None:
                raise RuntimeError(f"selected binding '{result}' has no AST declaration")
            value = _eval_expr(binding.expr, module)
            if isinstance(value, list):
                module._collections[result] = value
            else:
                module._bindings[result] = value
            continue

        if kind in {"sequence", "goal:transition"}:
            if strategy != "state-transition":
                raise RuntimeError(f"unsupported sequence runtime strategy {strategy!r}")
            op = sequences.get(result)
            if op is None:
                raise RuntimeError(f"selected sequence '{result}' has no AST declaration")
            value = _eval_expr(op.initial, module)
            generated = []
            for _ in range(op.steps):
                generated.append(value)
                if op.until is not None and bool(_eval_expr(op.until, module, local={"value": value})):
                    break
                if op.target is not None:
                    target = _eval_expr(op.target, module, local={"value": value})
                    candidates = [_eval_expr(expr, module, local={"value": value}) for expr in op.candidates]
                    constraints = op.constraints or ((op.constraint,) if op.constraint is not None else ())
                    if constraints:
                        candidates = [candidate for candidate in candidates if all(bool(_eval_expr(c, module, local={"value": value, "candidate": candidate})) for c in constraints)]
                        if not candidates:
                            break
                    value = min(candidates, key=lambda candidate: _goal_distance(candidate, target))
                else:
                    value = _eval_expr(op.expr, module, local={"value": value})
            module._collections[result] = generated
            continue

        if kind == "goal:select":
            if strategy != "goal-scan-select":
                raise RuntimeError(f"unsupported goal selection runtime strategy {strategy!r}")
            op = goals.get(result)
            if op is None or op.source not in module._collections:
                raise RuntimeError(f"goal source for '{result}' is unavailable")
            values = module._collections[op.source]
            candidates = values if isinstance(values, list) else [values]
            if op.predicate is not None:
                candidates = [row for row in candidates if bool(_eval_expr(op.predicate.expr, module, row))]
            if not candidates:
                raise TypeError(f"choose '{result}' found no matching value")
            key = lambda row: _eval_expr(op.key, module, row)
            module._collections[result] = min(candidates, key=key) if op.direction == "minimizing" else max(candidates, key=key)
            continue

        if kind == "goal:path":
            if strategy not in {"graph-shortest-path", "bidirectional-dijkstra", "a-star-landmark"}:
                raise RuntimeError(f"unsupported path runtime strategy {strategy!r}")
            op = paths.get(result)
            if op is None or op.source not in graphs:
                raise RuntimeError(f"unknown graph '{op.source if op else result}'")
            graph = graphs[op.source]
            if op.start == op.end:
                module._collections[result] = GraphPath((op.start,), 0.0)
                continue
            adj = {}
            for a, b, cost, bidir in graph.edges:
                adj.setdefault(a, []).append((b, cost))
                if bidir:
                    adj.setdefault(b, []).append((a, cost))
            if strategy == "graph-shortest-path":
                heap = [(0.0, op.start, (op.start,))]
                best = {op.start: 0.0}; found = None
                while heap:
                    cost, node, path = heapq.heappop(heap)
                    if cost != best.get(node): continue
                    if node == op.end:
                        found = GraphPath(path, cost); break
                    for nxt, weight in adj.get(node, ()):
                        new_cost = cost + weight
                        if new_cost < best.get(nxt, float("inf")):
                            best[nxt] = new_cost; heapq.heappush(heap, (new_cost, nxt, path + (nxt,)))
            elif strategy == "a-star-landmark":
                # ALT (A* with Landmarks and Triangle inequality). For an
                # undirected non-negative graph, |d(L,t)-d(L,v)| is admissible.
                vertices = sorted({v for edge in graph.edges for v in edge[:2]})
                landmark = next((v for v in vertices if v not in {op.start, op.end}), vertices[0] if vertices else op.start)
                dist_l = {landmark: 0.0}; landmark_heap = [(0.0, landmark)]
                while landmark_heap:
                    dc, dn = heapq.heappop(landmark_heap)
                    if dc != dist_l.get(dn): continue
                    for nxt, weight in adj.get(dn, ()):
                        nc = dc + weight
                        if nc < dist_l.get(nxt, float("inf")):
                            dist_l[nxt] = nc; heapq.heappush(landmark_heap, (nc, nxt))
                target_landmark = dist_l.get(op.end, float("inf"))
                def heuristic(node):
                    d = dist_l.get(node, float("inf"))
                    if d == float("inf") or target_landmark == float("inf"):
                        return 0.0
                    return abs(target_landmark - d)
                heap = [(heuristic(op.start), 0.0, op.start, (op.start,))]
                best = {op.start: 0.0}; found = None
                while heap:
                    _, cost, node, path = heapq.heappop(heap)
                    if cost != best.get(node): continue
                    if node == op.end:
                        found = GraphPath(path, cost); break
                    for nxt, weight in adj.get(node, ()):
                        new_cost = cost + weight
                        if new_cost < best.get(nxt, float("inf")):
                            best[nxt] = new_cost
                            heapq.heappush(heap, (new_cost + heuristic(nxt), new_cost, nxt, path + (nxt,)))
            else:
                # Exact bidirectional Dijkstra; legal only for proven undirected
                # graphs with non-negative edge costs.
                forward = [(0.0, op.start, (op.start,))]; backward = [(0.0, op.end, (op.end,))]
                dist_f, dist_b = {op.start: 0.0}, {op.end: 0.0}
                paths_f, paths_b = {op.start: (op.start,)}, {op.end: (op.end,)}
                best_cost, found = float("inf"), None
                settled_f, settled_b = set(), set()
                while forward and backward:
                    if forward[0][0] + backward[0][0] >= best_cost: break
                    if forward[0][0] <= backward[0][0]:
                        cost, node, path = heapq.heappop(forward)
                        if cost != dist_f.get(node) or node in settled_f: continue
                        settled_f.add(node)
                        if node in dist_b:
                            total = cost + dist_b[node]
                            if total < best_cost:
                                best_cost = total; found = GraphPath(path + tuple(reversed(paths_b[node]))[1:], total)
                        for nxt, weight in adj.get(node, ()):
                            nc = cost + weight
                            if nc < dist_f.get(nxt, float("inf")):
                                dist_f[nxt] = nc; paths_f[nxt] = path + (nxt,); heapq.heappush(forward, (nc, nxt, paths_f[nxt]))
                    else:
                        cost, node, path = heapq.heappop(backward)
                        if cost != dist_b.get(node) or node in settled_b: continue
                        settled_b.add(node)
                        if node in dist_f:
                            total = cost + dist_f[node]
                            if total < best_cost:
                                best_cost = total; found = GraphPath(paths_f[node] + tuple(reversed(path))[1:], total)
                        for nxt, weight in adj.get(node, ()):
                            nc = cost + weight
                            if nc < dist_b.get(nxt, float("inf")):
                                dist_b[nxt] = nc; paths_b[nxt] = path + (nxt,); heapq.heappush(backward, (nc, nxt, paths_b[nxt]))
            if found is None:
                raise TypeError(f"find path '{result}' found no path from {op.start} to {op.end}")
            module._collections[result] = found
            continue

        if kind == "goal:satisfy":
            if strategy not in {"constraint-enumeration", "constraint-propagation"}:
                raise RuntimeError(f"unsupported satisfy runtime strategy {strategy!r}")
            op = satisfies.get(result)
            if op is None:
                raise RuntimeError(f"selected satisfy goal '{result}' has no AST declaration")
            names = [v[0] for v in op.variables]
            from .goal_plan import propagate_integer_bounds
            bounds = propagate_integer_bounds(op.variables, op.constraints)

            if any(lo > hi for lo, hi in bounds.values()):
                raise TypeError(f"satisfy '{result}' found no solution")
            domains = [range(bounds[n][0], bounds[n][1] + 1) for n in names]
            solution = None
            for values in itertools.product(*domains):
                local = dict(zip(names, values))
                if all(bool(_eval_expr(c, module, local=local)) for c in op.constraints):
                    solution = local
                    break
            if solution is None:
                raise TypeError(f"satisfy '{result}' found no solution")
            module._collections[result] = solution
            continue

        raise RuntimeError(f"unsupported specialized goal IR kind '{kind}'")

    results = [o.result for o in module.ast.sequences] + [o.result for o in module.ast.goals] + [o.result for o in module.ast.path_goals] + [o.result for o in module.ast.satisfy_goals]
    if results:
        module._data_result_name = results[-1]
        module._data_result = module._collections[results[-1]]
    return module


def _can_plan_physics(module, pipeline) -> bool:
    """Whether the selected plan can execute the gravity domain directly."""
    if not (module.ast.gravity and module.ast.bodies):
        return False
    if module.ast.states or module.ast.state_sets or module.ast.conditional_pipelines:
        return False
    if module.ast.sequences or module.ast.goals or module.ast.path_goals or module.ast.satisfy_goals:
        return False
    if module.ast.filters or module.ast.sorts or module.ast.maps or module.ast.aggregates or module.ast.reduces:
        return False
    by = pipeline.optimized_ir.by_binding()
    allowed = {"physics.gravity", "effect:show"}
    return all(by[step.node].kind in allowed for step in pipeline.selected_execution_plan.steps)


def _execute_planned_physics(module, pipeline):
    """Execute the deterministic explicit-Euler gravity domain from the plan."""
    import math
    from .plan_runtime_support import Quantity

    if len(module.ast.simulations) != 1:
        # A gravity-only module may expose domain properties such as distance
        # or circle area without running a simulation. In that case the physics
        # node is an initialization/domain barrier and there is nothing to step.
        if module.ast.gravity and not module.ast.simulations:
            module.entities = {}
            module._bindings = {}
            module._states = {}
            return module
        raise RuntimeError("plan-runtime physics currently requires exactly one simulation")
    target_name, attractor_name, duration, step_size = module.simulation
    by_name = {body.name: body for body in module.bodies}
    target = by_name.get(target_name)
    attractor = by_name.get(attractor_name)
    if target is None or attractor is None:
        raise TypeError("simulate refers to unknown body")
    if "position" not in target.fields or "velocity" not in target.fields:
        raise TypeError(f"{target_name} requires position and velocity for gravity simulation")
    if "mass" not in attractor.fields:
        raise TypeError(f"{attractor_name} requires mass")

    # Match the verified reference interpreter exactly, including its remainder
    # step and explicit-Euler update ordering.
    steps = int(math.floor(duration / step_size + 1e-12))
    remainder = duration - steps * step_size
    G = 6.67430e-11
    for k in range(steps + (1 if remainder > 1e-12 else 0)):
        dt = step_size if k < steps else remainder
        position = target.fields["position"]
        velocity = target.fields["velocity"]
        mass = attractor.fields["mass"]
        acceleration = G * mass.value / (position.value * position.value)
        target.fields["velocity"] = Quantity(velocity.value + acceleration * dt, "mps")
        target.fields["position"] = Quantity(position.value + target.fields["velocity"].value * dt, "m")

    module.entities = {}
    module._bindings = {}
    module._states = {}
    module._physics_result = (target_name, attractor_name)
    # Shows are represented in the plan as ordered effects. Runtime execution
    # does not print here; CLI/show_value consumes the resulting body state.
    return module


def _install_plan_functions(module):
    """Install plan-runtime function values into the top-level runtime scope."""
    from .plan_expression import eval_expr as _eval_expr

    def eval_block(body, row=None, local=None):
        scope = dict(local or {})
        for stmt in body:
            if stmt.__class__.__name__ == "FunctionDecl":
                if stmt.name in scope:
                    raise TypeError(f"duplicate local variable '{stmt.name}'")
                scope[stmt.name] = _PlanFunctionValue(stmt, module, closure=scope, evaluator=eval_block)
            elif stmt.__class__.__name__ == "LetOp":
                if stmt.name in scope:
                    raise TypeError(f"duplicate local variable '{stmt.name}'")
                scope[stmt.name] = _eval_expr(stmt.expr, module, row=row, local=scope)
            elif stmt.__class__.__name__ == "ReturnOp":
                return _PlanReturnSignal(_eval_expr(stmt.expr, module, row=row, local=scope))
            elif stmt.__class__.__name__ == "IfOp":
                condition = _eval_expr(stmt.condition, module, row=row, local=scope)
                if not isinstance(condition, bool):
                    raise TypeError("if condition must evaluate to Boolean")
                branch = stmt.then_body if condition else stmt.else_body
                if branch:
                    signal = eval_block(branch, row=row, local=scope)
                    if isinstance(signal, _PlanReturnSignal):
                        return signal
            else:
                raise TypeError(f"unsupported statement {type(stmt).__name__}")
        return None

    module._plan_functions = {}
    for fn in module.ast.functions:
        value = _PlanFunctionValue(fn, module, closure=getattr(module, "_bindings", {}), evaluator=eval_block)
        module._plan_functions[fn.name] = value
        module._bindings[fn.name] = value

    # User-defined computed properties use the same plan-level block evaluator
    # as functions. The expression evaluator consults this table before its
    # reference-interpreter property path, so property bodies can themselves
    # call planned functions and other planned properties.
    module._plan_properties = {}
    for prop in module.ast.properties:
        def make_property_evaluator(decl):
            def evaluate(base):
                signal = eval_block(decl.body, local={"self": base})
                if isinstance(signal, _PlanReturnSignal):
                    return signal.value
                raise TypeError(f"property '{decl.entity_type}.{decl.name}' completed without return")
            return evaluate
        module._plan_properties[(prop.entity_type, prop.name)] = make_property_evaluator(prop)

    return module._plan_functions


def _can_plan_unified(module, pipeline) -> bool:
    """Whether one plan-runtime can execute the whole selected program.

    Unlike the earlier specialized dispatchers, this check deliberately permits
    mixed domains.  The runtime remains conservative about simulations and
    unsupported effectful nodes, but does not require the AST to belong to one
    domain only.
    """
    if not pipeline.selected_execution_plan.steps:
        return False
    allowed = {
        "function", "property", "binding", "filter", "sort", "map", "aggregate", "reduce",
        "conditional-pipeline", "state:init", "state:set", "state:read",
        "sequence", "goal:transition", "goal:select", "goal:path", "goal:satisfy",
        "physics.gravity", "effect:show",
    }
    by = pipeline.optimized_ir.by_binding()
    kinds = [by[step.node].kind for step in pipeline.selected_execution_plan.steps]
    if not all(kind in allowed for kind in kinds):
        return False
    domains = set()
    if module.ast.functions:
        domains.add("functions")
    if module.ast.properties:
        domains.add("properties")
    for kind in kinds:
        if kind == "function":
            domains.add("functions")
            continue
        if kind == "property":
            domains.add("properties")
            continue
        if kind in {"binding", "effect:show", "state:read"}:
            continue
        elif kind.startswith("state:"):
            domains.add("state")
        elif kind in {"filter", "sort", "map", "aggregate", "reduce", "conditional-pipeline"}:
            domains.add("collections")
        elif kind in {"sequence", "goal:transition", "goal:select", "goal:path", "goal:satisfy"}:
            domains.add("goals")
        elif kind == "physics.gravity":
            domains.add("physics")
    return bool(domains) and (len(domains) >= 2 or "functions" in domains or "properties" in domains)


def _execute_unified_plan(module, pipeline, allowed_nodes=None):
    """Execute a mixed S-Lang program directly from one selected plan.

    This is intentionally a semantic executor rather than a second optimizer.
    Individual strategies may still use conservative sequential implementations,
    but every operation is dispatched by the selected plan in dependency order.
    """
    import heapq
    import itertools
    import math
    from .plan_expression import eval_expr as _eval_expr, eval_pipeline_expr as _eval_pipeline_expr
    from .plan_runtime_support import _goal_distance, GraphPath, Quantity, qadd, qdiv

    steps = tuple(step for step in pipeline.selected_execution_plan.steps if allowed_nodes is None or step.node in allowed_nodes)

    fresh = not getattr(module, "_segment_runtime_initialized", False)
    if fresh:
        module.entities = {}
        module._bindings = {}
        module._collections = {name: list(rows) for name, rows in (module.data_tables or {}).items()}
        module._states = {}
        module._plan_runtime_active = True
        _install_plan_functions(module)
        module._segment_runtime_initialized = True

    bindings = {b.name: b for b in module.ast.bindings}
    states = {st.name: st for st in module.ast.states}
    state_sets = list(module.ast.state_sets)
    ops = _collection_operations(module)
    sequences = {o.result: o for o in module.ast.sequences}
    goals = {o.result: o for o in module.ast.goals}
    paths = {o.result: o for o in module.ast.path_goals}
    satisfies = {o.result: o for o in module.ast.satisfy_goals}
    graphs = {g.name: g for g in module.ast.graphs}
    by = pipeline.optimized_ir.by_binding()

    def plan_pipeline_expr(expr, row):
        value = _eval_expr(expr, module, row=row)
        if isinstance(value, _PlanFunctionValue):
            return value([row])
        return value

    def collection_step(kind, result, op, strategy):
        source = op.source
        if source not in module._collections:
            raise RuntimeError(f"collection source '{source}' is not available for '{result}'")
        values = module._collections[source]
        if kind == "filter":
            out = [row for row in values if bool(plan_pipeline_expr(op.predicate.expr, row))]
        elif kind == "map":
            out = [plan_pipeline_expr(op.expr, row) for row in values]
        elif kind == "sort":
            out = sorted(values, key=lambda row: plan_pipeline_expr(op.spec.expr, row), reverse=not op.spec.ascending)
        elif kind == "aggregate":
            vals = [plan_pipeline_expr(op.expr, row) for row in values]
            if op.operation == "count": out = len(vals)
            elif not vals: raise TypeError(f"aggregate '{op.operation}' cannot operate on an empty collection")
            elif op.operation in ("sum", "average", "avg"):
                out = vals[0]
                for value in vals[1:]: out = qadd(out, value) if hasattr(out, "unit") else out + value
                if op.operation in ("average", "avg"): out = qdiv(out, len(vals))
            elif op.operation == "max": out = max(vals)
            elif op.operation == "min": out = min(vals)
            else: raise TypeError(f"unknown aggregate operation '{op.operation}'")
        elif kind == "reduce":
            out = _eval_expr(op.initial, module)
            for item in values: out = _eval_expr(op.expr, module, row=item, local={"acc": out})
        else:
            raise RuntimeError(f"unsupported collection operation kind '{kind}'")
        module._collections[result] = out

    def conditional_step(result, op):
        condition = _eval_expr(op.condition, module)
        if not isinstance(condition, bool):
            raise TypeError("conditional pipeline condition must evaluate to Boolean")
        value = module._collections.get(op.source)
        if value is None:
            raise RuntimeError(f"collection source '{op.source}' is not available for '{result}'")
        for stage_kind, stage_expr in (op.then_stages if condition else op.else_stages):
            values = value if isinstance(value, list) else [value]
            if stage_kind == "where":
                value = [row for row in values if bool(plan_pipeline_expr(stage_expr.expr, row))]
            elif stage_kind == "map":
                value = [plan_pipeline_expr(stage_expr, row) for row in values]
            elif stage_kind == "sort":
                value = sorted(values, key=lambda row: plan_pipeline_expr(stage_expr.expr, row), reverse=not stage_expr.ascending)
            elif stage_kind == "aggregate":
                name, expr = stage_expr
                projected = [plan_pipeline_expr(expr, row) for row in values]
                if name == "count": value = len(projected)
                elif not projected: raise TypeError(f"aggregate '{name}' cannot operate on an empty collection")
                elif name in ("sum", "average", "avg"):
                    total = projected[0]
                    for item in projected[1:]: total = qadd(total, item) if hasattr(total, "unit") else total + item
                    value = qdiv(total, len(projected)) if name in ("average", "avg") else total
                elif name == "max": value = max(projected)
                elif name == "min": value = min(projected)
                else: raise TypeError(f"unknown aggregate operation '{name}'")
            elif stage_kind == "reduce":
                initial_expr, step_expr = stage_expr
                acc = _eval_expr(initial_expr, module)
                for item in values: acc = _eval_expr(step_expr, module, row=item, local={"acc": acc})
                value = acc
            else:
                raise RuntimeError(f"unknown conditional pipeline operation '{stage_kind}'")
        module._collections[result] = value

    def physics_step():
        if len(module.ast.simulations) != 1:
            raise RuntimeError("plan-runtime physics currently requires exactly one simulation")
        target_name, attractor_name, duration, step_size = module.simulation
        by_name = {body.name: body for body in module.bodies}
        target, attractor = by_name.get(target_name), by_name.get(attractor_name)
        if target is None or attractor is None: raise TypeError("simulate refers to unknown body")
        if "position" not in target.fields or "velocity" not in target.fields: raise TypeError(f"{target_name} requires position and velocity for gravity simulation")
        if "mass" not in attractor.fields: raise TypeError(f"{attractor_name} requires mass")
        steps = int(math.floor(duration / step_size + 1e-12))
        remainder = duration - steps * step_size
        G = 6.67430e-11
        for k in range(steps + (1 if remainder > 1e-12 else 0)):
            dt = step_size if k < steps else remainder
            position, velocity, mass = target.fields["position"], target.fields["velocity"], attractor.fields["mass"]
            acceleration = G * mass.value / (position.value * position.value)
            target.fields["velocity"] = Quantity(velocity.value + acceleration * dt, "mps")
            target.fields["position"] = Quantity(position.value + target.fields["velocity"].value * dt, "m")
        module._physics_result = (target_name, attractor_name)

    for step in pipeline.selected_execution_plan.steps:
        node, kind = step.node, by[step.node].kind
        result = _binding_name(node)
        if kind in {"function", "property", "effect:show", "state:read"}:
            continue
        if kind in {"binding", "group"}:
            binding = bindings.get(result)
            if binding is None: raise RuntimeError(f"selected binding '{result}' has no AST declaration")
            value = _eval_expr(binding.expr, module)
            if isinstance(value, list): module._collections[result] = value
            else: module._bindings[result] = value
        elif kind == "state:init":
            name = node.split(":", 2)[1]
            state = states.get(name)
            if state is None: raise RuntimeError(f"selected state '{name}' has no AST declaration")
            module._states[name] = _eval_expr(state.expr, module)
        elif kind == "state:set":
            base = node.rsplit("#", 1)[0]
            parts = base.split(":")
            name = parts[1] if len(parts) > 1 else ""
            occurrence = int(parts[-1]) if parts and parts[-1].isdigit() else 1
            candidates = [x for x in state_sets if x.name == name]
            if not candidates: raise RuntimeError(f"selected state write '{node}' has no AST declaration")
            op = candidates[min(occurrence, len(candidates)) - 1]
            module._states[name] = _eval_expr(op.expr, module)
        elif kind in {"filter", "sort", "map", "aggregate", "reduce"}:
            collection_step(kind, result, ops[kind][result], step.strategy)
        elif kind == "conditional-pipeline":
            conditional_step(result, ops[kind][result])
        elif kind in {"sequence", "goal:transition"}:
            op = sequences[result]
            value, generated = _eval_expr(op.initial, module), []
            for _ in range(op.steps):
                generated.append(value)
                if op.until is not None and bool(_eval_expr(op.until, module, local={"value": value})): break
                if op.target is not None:
                    target = _eval_expr(op.target, module, local={"value": value})
                    candidates = [_eval_expr(expr, module, local={"value": value}) for expr in op.candidates]
                    constraints = op.constraints or ((op.constraint,) if op.constraint is not None else ())
                    candidates = [c for c in candidates if all(bool(_eval_expr(x, module, local={"value": value, "candidate": c})) for x in constraints)] if constraints else candidates
                    if not candidates: break
                    value = min(candidates, key=lambda c: _goal_distance(c, target))
                else: value = _eval_expr(op.expr, module, local={"value": value})
            module._collections[result] = generated
        elif kind == "goal:select":
            op = goals[result]; values = module._collections[op.source]; values = values if isinstance(values, list) else [values]
            if op.predicate is not None: values = [row for row in values if bool(_eval_expr(op.predicate.expr, module, row))]
            if not values: raise TypeError(f"choose '{result}' found no matching value")
            key=lambda row: _eval_expr(op.key, module, row)
            module._collections[result] = min(values, key=key) if op.direction == "minimizing" else max(values, key=key)
        elif kind == "goal:path":
            op=paths[result]; graph=graphs[op.source]
            if op.start == op.end: module._collections[result]=GraphPath((op.start,),0.0); continue
            adj={}
            for a,b,c,bidir in graph.edges:
                adj.setdefault(a,[]).append((b,c))
                if bidir: adj.setdefault(b,[]).append((a,c))
            heap=[(0.0,op.start,(op.start,))]; best={op.start:0.0}; found=None
            while heap:
                cost,n,path=heapq.heappop(heap)
                if cost != best.get(n): continue
                if n==op.end: found=GraphPath(path,cost); break
                for nxt,w in adj.get(n,()):
                    nc=cost+w
                    if nc < best.get(nxt,float("inf")):
                        best[nxt]=nc; heapq.heappush(heap,(nc,nxt,path+(nxt,)))
            if found is None: raise TypeError(f"find path '{result}' found no path from {op.start} to {op.end}")
            module._collections[result]=found
        elif kind == "goal:satisfy":
            op=satisfies[result]; names=[v[0] for v in op.variables]; domains=[range(v[1],v[2]+1) for v in op.variables]
            solution=None
            for values in itertools.product(*domains):
                local=dict(zip(names,values))
                if all(bool(_eval_expr(c,module,local=local)) for c in op.constraints): solution=local; break
            if solution is None: raise TypeError(f"satisfy '{result}' found no solution")
            module._collections[result]=solution
        elif kind == "physics.gravity":
            physics_step()
        else:
            raise RuntimeError(f"unsupported unified plan IR kind '{kind}'")

    candidates = [o.result for o in module.ast.filters] + [o.result for o in module.ast.sorts] + [o.result for o in module.ast.maps] + [o.result for o in module.ast.aggregates] + [o.result for o in module.ast.reduces] + [o.result for o in module.ast.conditional_pipelines] + [o.result for o in module.ast.sequences] + [o.result for o in module.ast.goals] + [o.result for o in module.ast.path_goals] + [o.result for o in module.ast.satisfy_goals]
    if candidates:
        module._data_result_name = candidates[-1]
        module._data_result = module._collections.get(candidates[-1], module._bindings.get(candidates[-1]))
    return module

def _segment_execution_mode(pipeline):
    """Return the selected plan segments and enforce their coverage/order.

    Segmentation is an execution artifact, not merely diagnostic metadata.
    Every selected step must belong to exactly one contiguous segment and the
    concatenation of segment nodes must equal the selected plan order.
    """
    segments = pipeline.selected_execution_plan.segments
    selected = tuple(step.node for step in pipeline.selected_execution_plan.steps)
    covered = tuple(node for segment in segments for node in segment.nodes)
    if covered != selected:
        raise ValueError("execution segments do not cover selected plan in order")
    if any(not segment.nodes for segment in segments):
        raise ValueError("execution plan contains an empty segment")
    from .segment_bridge import validate_segment_dependencies
    validate_segment_dependencies(segments, pipeline.dependency_graph.edges)
    for index, segment in enumerate(segments):
        if segment.index != index:
            raise ValueError("execution segment indices are not contiguous")
    return segments


def _execute_segmented(module, pipeline):
    """Execute the selected plan through explicit runtime segments.

    Fully supported plans are executed by the unified executor while the
    segment boundary is validated and recorded. If a future capability audit
    introduces a reference segment, the boundary is isolated here rather than
    silently falling back from the whole runtime. Until a per-node reference
    bridge exists, mixed plans fail explicitly instead of re-running the whole
    program and violating segment semantics.
    """
    segments = _segment_execution_mode(pipeline)
    from .segment_bridge import capture, execute_reference_segment, validate_segment_contracts
    fallback = [s for s in segments if s.mode == "reference-interpreter"]
    # The bridge executes segments in plan order.  A plan-runtime segment is
    # executed against the shared namespace; a fallback segment receives an
    # explicit handoff snapshot and must mutate that same namespace through a
    # registered segment adapter.  No fallback may restart the whole program.
    if not fallback:
        _execute_unified_plan(module, pipeline)
        return module, "plan-runtime-segmented"

    node_kinds = {n.binding: n.kind for n in pipeline.optimized_ir.nodes}
    contracts = {segment.index: segment.data_contract for segment in segments if segment.data_contract is not None}
    if len(contracts) != len(segments):
        # Compatibility for externally assembled/manual segment plans. Compiler-
        # produced plans already carry static contracts in the selected plan.
        from .segment_bridge import build_segment_data_contracts
        contracts = build_segment_data_contracts(
            segments, pipeline.dependency_graph.edges, pipeline.optimized_ir,
            external_names=tuple((getattr(module, "data_tables", {}) or {}).keys()),
        )
    validate_segment_contracts(segments, contracts, pipeline.dependency_graph.edges, ir=pipeline.optimized_ir)
    runtime_executor = getattr(module, "_segment_reference_executor", None)
    if runtime_executor is None:
        from .reference_runtime import segment_executor as runtime_executor
    for segment in segments:
        contract = contracts.get(segment.index)
        from .segment_bridge import _state_snapshot, validate_runtime_state_boundary
        state_names = set(contract.state_inputs if contract else ()) | set(contract.state_outputs if contract else ())
        state_before = _state_snapshot(getattr(module, "_states", {}) or {}, state_names)
        # Validate required state before entering either execution backend.
        if contract is not None:
            for name in contract.state_inputs:
                if name not in (getattr(module, "_states", {}) or {}):
                    raise RuntimeError(f"segment {segment.index} missing runtime state input: {name!r}")
        handoff = capture(module, segment.index, segment.mode, contract)
        if segment.mode == "plan-runtime":
            _execute_unified_plan(module, pipeline, allowed_nodes=set(segment.nodes))
        else:
            if getattr(module, "_segment_reference_executor", None) is None:
                from .segment_bridge import validate_reference_adapter
                from .reference_runtime import segment_executor_registry
                node_kinds = {n.binding: n.kind for n in pipeline.optimized_ir.nodes}
                validate_reference_adapter(segment, node_kinds, segment_executor_registry())
            execute_reference_segment(module, segment, handoff, executor=runtime_executor)
        validate_runtime_state_boundary(module, contract, state_before, segment_index=segment.index)
    return module, "plan-runtime-segmented-bridge"


def _execute(module, execution_profile=None, backend_supported_strategies=None):
    """Internal execution implementation; callers enter a runtime execution context.

    The runtime uses the selected plan for bindings, user-defined function
    bodies, collection strategies, stateful transitions, goals, physics, and
    supported observation boundaries. Unsupported constructs continue through
    the verified reference interpreter.
    """
    profile = execution_profile
    pipeline = compile_semantic_pipeline(
        module.ast,
        backend_supported_strategies=backend_supported_strategies,
        execution_profile=profile,
    ) if profile is not None else compile_semantic_pipeline(
        module.ast,
        backend_supported_strategies=backend_supported_strategies,
    )
    validate_runtime_plan(pipeline)
    segments = _segment_execution_mode(pipeline)
    if segments and (_can_plan_unified(module, pipeline) or any(s.mode == "reference-interpreter" for s in segments)):
        _execute_segmented(module, pipeline)
        executor = "plan-runtime-segmented-bridge" if any(s.mode == "reference-interpreter" for s in segments) else "plan-runtime-segmented"
    elif _can_plan_collections(module, pipeline):
        _execute_planned_collections(module, pipeline)
        executor = "plan-runtime-conditional" if module.ast.conditional_pipelines else "plan-runtime-specialized"
    elif _can_plan_stateful(module, pipeline):
        _execute_planned_stateful(module, pipeline)
        executor = "plan-runtime-stateful"
    elif _can_plan_specialized_goals(module, pipeline):
        _execute_specialized_goals(module, pipeline)
        executor = "plan-runtime-goals"
    elif _can_plan_physics(module, pipeline):
        _execute_planned_physics(module, pipeline)
        executor = "plan-runtime-physics"
    elif _can_plan_bindings(module, pipeline):
        _execute_planned_bindings(module, pipeline)
        executor = "plan-runtime"
    else:
        from .reference_runtime import execute as reference_execute
        reference_execute(module)
        executor = "reference-interpreter"
    trace = build_runtime_trace(pipeline, executor=executor)
    return module, trace

def execute(
    module,
    execution_profile=None,
    backend_supported_strategies=None,
    max_events=None,
    max_duration_ms=None,
):
    """Execute one complete S-Lang program inside one runtime execution context."""
    from .stdlib_runtime import runtime_execution_context
    with runtime_execution_context(max_events=max_events, max_duration_ms=max_duration_ms):
        return _execute(
            module,
            execution_profile=execution_profile,
            backend_supported_strategies=backend_supported_strategies,
        )


def format_runtime_trace(trace: RuntimeTrace) -> str:
    lines = ["runtime.trace {"]
    for step in trace.steps:
        lines.append(
            f"  level {step.level}: {step.node} strategy={step.strategy} status={step.status}"
        )
    lines.append(f"  operations = {trace.operation_count}")
    lines.append(f"  completed = {trace.completed}")
    lines.append("  deterministic = yes" if trace.deterministic else "  deterministic = no")
    lines.append(f"  executor = {trace.executor}")
    lines.append("}")
    return "\n".join(lines)
