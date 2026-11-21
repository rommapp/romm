"""Find the HTTP error statuses each route can raise, by static call-graph analysis."""

from __future__ import annotations

import ast
import inspect
import re
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from fastapi.routing import APIRoute

BACKEND = Path(__file__).resolve().parent.parent
STATUS_ATTR = re.compile(r"HTTP_(\d{3})_")


@dataclass
class Module:
    name: str
    tree: ast.Module
    # Maps a local name to the (module, name) it was imported from, or to
    # (module, None) when it names a module.
    imports: dict[str, tuple[str, str | None]] = field(default_factory=dict)
    functions: dict[str, ast.FunctionDef | ast.AsyncFunctionDef] = field(
        default_factory=dict
    )
    classes: dict[str, ast.ClassDef] = field(default_factory=dict)
    # The value of each module-level `name = value` assignment.
    assigns: dict[str, ast.expr] = field(default_factory=dict)


def _module_name(path: Path) -> str:
    parts = path.relative_to(BACKEND).with_suffix("").parts
    return ".".join(parts[:-1] if parts[-1] == "__init__" else parts)


def _absolute(module: str, is_package: bool, level: int, target: str | None) -> str:
    if not level:
        return target or ""
    base = module.split(".")
    base = base if is_package else base[:-1]
    base = base[: len(base) - (level - 1)]
    return ".".join([*base, target] if target else base)


@cache
def load(name: str) -> Module | None:
    rel = Path(*name.split("."))
    for path in (BACKEND / rel / "__init__.py", BACKEND / rel.with_suffix(".py")):
        if path.is_file():
            break
    else:
        return None
    tree = ast.parse(path.read_text())
    mod = Module(name, tree)
    is_package = path.name == "__init__.py"
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            src = _absolute(name, is_package, node.level, node.module)
            for alias in node.names:
                mod.imports[alias.asname or alias.name] = (src, alias.name)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                local = alias.asname or alias.name.split(".")[0]
                mod.imports[local] = (alias.asname and alias.name or local, None)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            mod.functions[node.name] = node
        elif isinstance(node, ast.ClassDef):
            mod.classes[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    mod.assigns[target.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            if node.value is not None:
                mod.assigns[node.target.id] = node.value
    return mod


# A resolved symbol: ("func", module, qualname), ("class", module, name),
# ("module", module, ""), or ("value", module, name) for a module-level assignment.
Symbol = tuple[str, str, str]


@cache
def resolve(module: str, name: str, depth: int = 0) -> Symbol | None:
    """What `name` means at the top level of `module`."""
    mod = load(module)
    if mod is None or depth > 10:
        return None
    if name in mod.functions:
        return ("func", module, name)
    if name in mod.classes:
        return ("class", module, name)
    if name in mod.assigns:
        return ("value", module, name)
    if name in mod.imports:
        src, attr = mod.imports[name]
        if attr is None:
            return ("module", src, "") if load(src) else None
        if load(f"{src}.{attr}"):
            return ("module", f"{src}.{attr}", "")
        return resolve(src, attr, depth + 1)
    return None


def _class_of_value(module: str, name: str) -> Symbol | None:
    """The class a module-level `name = SomeClass(...)` instantiates."""
    mod = load(module)
    value = mod.assigns.get(name) if mod else None
    if isinstance(value, ast.Call):
        target = _resolve_expr(module, None, value.func)
        if target and target[0] == "class":
            return target
    return None


def _method(cls: Symbol, attr: str, depth: int = 0) -> Symbol | None:
    """Find `attr` on a class or its bases."""
    _, module, name = cls
    mod = load(module)
    node = mod.classes.get(name) if mod else None
    if node is None or depth > 10:
        return None
    for item in node.body:
        if (
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == attr
        ):
            return ("func", module, f"{name}.{attr}")
    for base in node.bases:
        base_sym = _resolve_expr(module, None, base)
        if base_sym and base_sym[0] == "class":
            found = _method(base_sym, attr, depth + 1)
            if found:
                return found
    return None


def _resolve_expr(module: str, owner: str | None, expr: ast.expr) -> Symbol | None:
    """Resolve a call target. `owner` is the enclosing class, used to resolve `self` and `cls`."""
    if isinstance(expr, ast.Name):
        if expr.id in ("self", "cls") and owner:
            return ("class", module, owner)
        return resolve(module, expr.id)
    if isinstance(expr, ast.Attribute):
        base = _resolve_expr(module, owner, expr.value)
        if base is None:
            return None
        kind, base_module, base_name = base
        if kind == "module":
            return resolve(base_module, expr.attr)
        if kind == "value":
            cls = _class_of_value(base_module, base_name)
            return _method(cls, expr.attr) if cls else None
        if kind == "class":
            return _method(base, expr.attr)
    return None


def _status(node: ast.expr | None) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Attribute):
        match = STATUS_ATTR.match(node.attr)
        if match:
            return int(match.group(1))
    return None


def _subclasses_http_exception(module: str, owner: str | None) -> bool:
    mod = load(module)
    cls = mod.classes.get(owner) if mod and owner else None
    return cls is not None and any(
        getattr(base, "id", getattr(base, "attr", None)) == "HTTPException"
        for base in cls.bases
    )


def _http_exception_status(
    call: ast.Call, module: str = "", owner: str | None = None
) -> int | None:
    """The status of `HTTPException(...)`, or of `super().__init__(...)` in a subclass."""
    func = call.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    is_super_init = (
        name == "__init__"
        and isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Call)
        and getattr(func.value.func, "id", None) == "super"
        and _subclasses_http_exception(module, owner)
    )
    if name != "HTTPException" and not is_super_init:
        return None
    for kw in call.keywords:
        if kw.arg == "status_code":
            return _status(kw.value)
    return _status(call.args[0]) if call.args else None


def _function_node(sym: Symbol) -> tuple[ast.AST, str | None] | None:
    _, module, qualname = sym
    mod = load(module)
    if mod is None:
        return None
    if "." not in qualname:
        node = mod.functions.get(qualname)
        return (node, None) if node else None
    owner, attr = qualname.split(".", 1)
    cls = mod.classes.get(owner)
    for item in cls.body if cls else []:
        if (
            isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            and item.name == attr
        ):
            return item, owner
    return None


def _body_nodes(fn: ast.AST) -> list[ast.AST]:
    """Every node of a function except its decorators."""
    if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        roots: list[ast.AST] = [fn.args, *fn.body]
        return [n for root in roots for n in ast.walk(root)]
    return list(ast.walk(fn))


_memo: dict[Symbol, frozenset[int]] = {}


def _dependency(node: ast.Call) -> ast.expr | None:
    """The callable a `Depends(...)` or `Security(...)` call injects."""
    func = node.func
    name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
    if name not in ("Depends", "Security"):
        return None
    for kw in node.keywords:
        if kw.arg == "dependency":
            return kw.value
    return node.args[0] if node.args else None


def _annotation_names(fn: ast.AST) -> list[ast.Name]:
    """Names in a function's parameter annotations, where `Annotated` aliases sit."""
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    params = [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]
    return [
        node
        for param in params
        if param.annotation is not None
        for node in ast.walk(param.annotation)
        if isinstance(node, ast.Name)
    ]


def statuses(sym: Symbol, stack: frozenset[Symbol] = frozenset()) -> frozenset[int]:
    """Error statuses a function, class constructor or value can raise."""
    if sym in _memo:
        return _memo[sym]
    if sym in stack:
        return frozenset()
    stack = stack | {sym}
    kind, module, name = sym
    found: set[int] = set()
    if kind == "value":
        value = load(module).assigns[name]  # type: ignore[union-attr]
        if isinstance(value, ast.Call):
            code = _http_exception_status(value)
            if code:
                found.add(code)
        for node in ast.walk(value):
            dependency = _dependency(node) if isinstance(node, ast.Call) else None
            target = _resolve_expr(module, None, dependency) if dependency else None
            if target and target[0] == "func":
                found |= statuses(target, stack)
    elif kind == "class":
        init = _method(sym, "__init__")
        if init:
            found |= statuses(init, stack)
    elif kind == "func":
        located = _function_node(sym)
        if located:
            fn, owner = located
            for node in _body_nodes(fn):
                if isinstance(node, ast.Call):
                    code = _http_exception_status(node, module, owner)
                    if code:
                        found.add(code)
                        continue
                    target = _resolve_expr(module, owner, node.func)
                    if target and target[0] != "module":
                        found |= statuses(target, stack)
                    dependency = _dependency(node)
                    target = (
                        _resolve_expr(module, owner, dependency) if dependency else None
                    )
                    if target and target[0] == "func":
                        found |= statuses(target, stack)
                elif isinstance(node, ast.Raise) and isinstance(
                    node.exc, (ast.Name, ast.Attribute)
                ):
                    target = _resolve_expr(module, owner, node.exc)
                    if target and target[0] in ("value", "class"):
                        found |= statuses(target, stack)
            for name_node in _annotation_names(fn):
                target = _resolve_expr(module, owner, name_node)
                if target and target[0] == "value":
                    found |= statuses(target, stack)
    result = frozenset(c for c in found if c >= 400)
    _memo[sym] = result
    return result


def api_routes(routes: Iterable[Any]) -> Iterator[APIRoute]:
    """Every APIRoute, including those in nested routers."""
    for route in routes:
        if hasattr(route, "original_router"):
            yield from api_routes(route.original_router.routes)
        elif isinstance(route, APIRoute):
            yield route


def undocumented(routes: Iterable[Any]) -> dict[str, list[int]]:
    """Map each route's `module:function` to the statuses it raises that its `responses` leaves out."""
    gaps: dict[str, set[int]] = {}
    for route in api_routes(routes):
        endpoint = inspect.unwrap(route.endpoint)
        documented = {int(code) for code in route.responses} | {422}
        raised = statuses(("func", endpoint.__module__, endpoint.__name__))
        missing = raised - documented
        if missing:
            key = f"{endpoint.__module__}:{endpoint.__name__}"
            gaps.setdefault(key, set()).update(missing)
    return {key: sorted(codes) for key, codes in sorted(gaps.items())}


def main() -> int:
    from main import app  # noqa: PLC0415

    for key, codes in undocumented(app.routes).items():
        print(key, codes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
