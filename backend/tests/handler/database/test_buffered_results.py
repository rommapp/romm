import ast

from tests.app_sources import app_sources

RESULT_METHODS = {"execute", "scalars"}
RESULT_VIEWS = {"scalars", "mappings", "tuples", "unique", "columns"}
CONSUMERS = {
    "all",
    "any",
    "dict",
    "enumerate",
    "filter",
    "frozenset",
    "iter",
    "list",
    "map",
    "max",
    "min",
    "next",
    "set",
    "sorted",
    "sum",
    "tuple",
    "zip",
}
# Methods that iterate their argument, as in `ids.update(session.scalars(...))`.
ITERATING_METHODS = {"extend", "join", "union", "update"}

type Parents = dict[ast.AST, ast.AST]


def _view_root(node: ast.AST, parents: Parents) -> ast.AST:
    """The outermost `.scalars()`-like view of `node`, which iterates the same cursor."""
    while (
        isinstance(attr := parents.get(node), ast.Attribute)
        and attr.attr in RESULT_VIEWS
        and isinstance(call := parents.get(attr), ast.Call)
    ):
        node = call
    return node


def _is_iterated(node: ast.AST, parents: Parents) -> bool:
    parent = parents.get(node)
    if isinstance(parent, (ast.For, ast.comprehension)):
        return parent.iter is node
    if isinstance(parent, (ast.YieldFrom, ast.Starred)):
        return True
    if isinstance(parent, ast.Assign):
        return any(isinstance(t, (ast.Tuple, ast.List)) for t in parent.targets)
    if isinstance(parent, ast.Call) and node in parent.args:
        func = parent.func
        return (isinstance(func, ast.Name) and func.id in CONSUMERS) or (
            isinstance(func, ast.Attribute) and func.attr in ITERATING_METHODS
        )
    return False


def _bound_name(node: ast.AST, parents: Parents) -> str | None:
    """The name `node` is bound to by `with ... as name` or an assignment."""
    parent = parents.get(node)
    target: ast.AST | None = None
    if isinstance(parent, ast.withitem):
        target = parent.optional_vars
    elif isinstance(parent, ast.Assign) and len(parent.targets) == 1:
        target = parent.targets[0]
    elif isinstance(parent, (ast.AnnAssign, ast.NamedExpr)):
        target = parent.target
    return target.id if isinstance(target, ast.Name) else None


def _scope(node: ast.AST, parents: Parents) -> ast.AST:
    while not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
        node = parents[node]
    return node


def _iterated_results(tree: ast.AST) -> list[int]:
    """Lines where a query Result is iterated, directly or through a name."""
    parents = {
        child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)
    }
    lines = []
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in RESULT_METHODS
            and node.args
        ):
            continue
        outer = _view_root(node, parents)
        if _is_iterated(outer, parents):
            lines.append(node.lineno)
        elif name := _bound_name(outer, parents):
            if any(
                isinstance(use, ast.Name)
                and use.id == name
                and isinstance(use.ctx, ast.Load)
                and _is_iterated(_view_root(use, parents), parents)
                for use in ast.walk(_scope(outer, parents))
            ):
                lines.append(node.lineno)
    return lines


def test_query_results_are_not_left_for_the_gc():
    # An iterated Result sits in a cycle the GC frees on another thread, segfaulting
    # mariadb. Closing it only helps ORM results; `.all()`/`.partitions()` make none.
    offenders = []
    for relative, tree in app_sources():
        offenders += [f"{relative}:{line}" for line in _iterated_results(tree)]

    assert offenders == []
