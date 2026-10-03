import ast
from pathlib import Path

BACKEND_ROOT = Path(__file__).parents[3]
RESULT_METHODS = {"execute", "scalars"}
RESULT_VIEWS = {"scalars", "mappings", "tuples", "unique", "columns"}
CONSUMERS = {
    "all",
    "any",
    "dict",
    "enumerate",
    "frozenset",
    "iter",
    "list",
    "max",
    "min",
    "next",
    "set",
    "sorted",
    "sum",
    "tuple",
    "zip",
}


def _iterated_results(tree: ast.AST) -> list[int]:
    """Lines where a query Result is iterated without `.all()` or a `with` block."""
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
        # Follow `.scalars()` and similar views, which iterate the same cursor.
        outer = node
        while (
            isinstance(attr := parents.get(outer), ast.Attribute)
            and attr.attr in RESULT_VIEWS
            and isinstance(call := parents.get(attr), ast.Call)
        ):
            outer = call
        parent = parents.get(outer)
        if (
            isinstance(parent, (ast.For, ast.comprehension)) and parent.iter is outer
        ) or (
            isinstance(parent, ast.Call)
            and isinstance(parent.func, ast.Name)
            and parent.func.id in CONSUMERS
            and outer in parent.args
        ):
            lines.append(node.lineno)
    return lines


def test_query_results_are_not_left_for_the_gc():
    # An iterated Result sits in a reference cycle, and the cyclic GC frees its
    # cursor on another thread, which segfaults the mariadb connector.
    offenders = []
    for path in BACKEND_ROOT.rglob("*.py"):
        relative = path.relative_to(BACKEND_ROOT)
        if relative.parts[0] in {"tests", "alembic"}:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        offenders += [f"{relative}:{line}" for line in _iterated_results(tree)]

    assert offenders == []
