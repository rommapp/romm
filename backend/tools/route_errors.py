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

from fastapi.dependencies.utils import get_flat_params
from fastapi.routing import APIRoute

from decorators.auth import SCOPE_ERRORS

BACKEND = Path(__file__).resolve().parent.parent
STATUS_ATTR = re.compile(r"HTTP_(\d{3})_")
# Responses a route returns instead of raising, whose status reaches the client.
RESPONSE_CLASSES = frozenset(
    {
        "FileResponse",
        "HTMLResponse",
        "JSONResponse",
        "ORJSONResponse",
        "PlainTextResponse",
        "RedirectResponse",
        "Response",
        "StreamingResponse",
    }
)
# Stands for a status the analyzer cannot read, such as one copied from an upstream
# response. A route that reaches one fails the check until the line declares it.
UNREADABLE_STATUS = 0
# Marks code whose errors never reach the client. Put it at the end of the line, or
# on the line above, with the reason after it.
IGNORE_MARKER = "# route-errors: ignore"
# Declares the statuses a line raises, such as `# route-errors: raises 409, 423`, in
# place of what the analyzer reads there. For a status it cannot follow or read.
RAISES_MARKER = re.compile(r"# route-errors: raises (\d{3}(?:, *\d{3})*)")


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
    # Lines whose code `IGNORE_MARKER` leaves out of the analysis.
    ignored: set[int] = field(default_factory=set)
    # The statuses `RAISES_MARKER` declares, by line.
    declared: dict[int, set[int]] = field(default_factory=dict)


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
    source = path.read_text()
    tree = ast.parse(source)
    mod = Module(name, tree)
    for number, line in enumerate(source.splitlines(), start=1):
        marked = number + 1 if line.lstrip().startswith("#") else number
        match = RAISES_MARKER.search(line)
        if IGNORE_MARKER in line or match:
            mod.ignored.add(marked)
        if match:
            codes = {int(code) for code in re.findall(r"\d{3}", match.group(1))}
            mod.declared.setdefault(marked, set()).update(codes)
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


def _call_name(call: ast.Call) -> str | None:
    """The name a call ends in, such as `to_thread` for `asyncio.to_thread(...)`."""
    func = call.func
    return func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)


def _status(node: ast.expr | None) -> int | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, int):
        return node.value
    if isinstance(node, ast.Attribute):
        match = STATUS_ATTR.match(node.attr)
        if match:
            return int(match.group(1))
    return None


@dataclass(frozen=True)
class Codes:
    """What a status expression can evaluate to."""

    codes: frozenset[int] = frozenset()
    # Parameters of the enclosing function that the status comes from.
    params: frozenset[str] = frozenset()
    # True when part of the expression cannot be read statically.
    unreadable: bool = False

    def __or__(self, other: Codes) -> Codes:
        return Codes(
            self.codes | other.codes,
            self.params | other.params,
            self.unreadable or other.unreadable,
        )


def _param_names(fn: ast.AST) -> list[str]:
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    return [a.arg for a in [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]]


def _local_values(fn: ast.AST, name: str) -> list[ast.expr]:
    """Every value assigned to the local `name` in `fn`."""
    return [
        node.value
        for node in ast.walk(fn)
        if isinstance(node, (ast.Assign, ast.AnnAssign))
        and node.value is not None
        and any(
            isinstance(target, ast.Name) and target.id == name
            for target in (
                node.targets if isinstance(node, ast.Assign) else [node.target]
            )
        )
    ]


def _module_dict(module: str, expr: ast.expr) -> ast.Dict | None:
    """The literal dict a module-level name holds, such as a map of errors to statuses."""
    if not isinstance(expr, ast.Name):
        return None
    sym = resolve(module, expr.id)
    mod = load(sym[1]) if sym and sym[0] == "value" else None
    value = mod.assigns.get(sym[2]) if mod and sym else None
    return value if isinstance(value, ast.Dict) else None


def _codes(expr: ast.expr | None, module: str, fn: ast.AST, depth: int = 0) -> Codes:
    """The statuses a `status_code` expression in `fn` can take."""
    if expr is None or depth > 10:
        return Codes(unreadable=True)
    code = _status(expr)
    if code is not None:
        return Codes(frozenset({code}))
    if isinstance(expr, ast.IfExp):
        return _codes(expr.body, module, fn, depth + 1) | _codes(
            expr.orelse, module, fn, depth + 1
        )
    lookup = None
    default = None
    if isinstance(expr, ast.Subscript):
        lookup = _module_dict(module, expr.value)
    elif (
        isinstance(expr, ast.Call)
        and isinstance(expr.func, ast.Attribute)
        and expr.func.attr == "get"
    ):
        lookup = _module_dict(module, expr.func.value)
        default = expr.args[1] if len(expr.args) > 1 else None
    if lookup is not None:
        found = Codes()
        for value in [*lookup.values, *([default] if default else [])]:
            found |= _codes(value, module, fn, depth + 1)
        return found
    if isinstance(expr, ast.Name):
        if expr.id in _param_names(fn):
            return Codes(params=frozenset({expr.id}))
        values = _local_values(fn, expr.id)
        if values:
            found = Codes()
            for value in values:
                found |= _codes(value, module, fn, depth + 1)
            return found
    return Codes(unreadable=True)


def _subclasses_http_exception(module: str, owner: str | None) -> bool:
    mod = load(module)
    cls = mod.classes.get(owner) if mod and owner else None
    return cls is not None and any(
        getattr(base, "id", getattr(base, "attr", None)) == "HTTPException"
        for base in cls.bases
    )


def _status_expr(
    call: ast.Call, module: str = "", owner: str | None = None
) -> ast.expr | None:
    """The status argument of an `HTTPException`, a subclass's `super().__init__` or a response."""
    func = call.func
    name = _call_name(call)
    is_super_init = (
        name == "__init__"
        and isinstance(func, ast.Attribute)
        and isinstance(func.value, ast.Call)
        and getattr(func.value.func, "id", None) == "super"
        and _subclasses_http_exception(module, owner)
    )
    if name == "HTTPException" or is_super_init:
        position = 0
    elif name in RESPONSE_CLASSES:
        position = 1
    else:
        return None
    for kw in call.keywords:
        if kw.arg == "status_code":
            return kw.value
    return call.args[position] if len(call.args) > position else None


def _http_exception_status(call: ast.Call) -> int | None:
    """The status of a module-level `HTTPException(...)` instance."""
    name = _call_name(call)
    if name != "HTTPException":
        return None
    expr = _status_expr(call)
    return _status(expr) if expr is not None else None


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


# Calls that run the function in one of their arguments and re-raise its errors,
# mapped to that argument's position.
OFFLOADS = {"to_thread": 0, "run_in_threadpool": 0, "run_sync": 0, "run_in_executor": 1}


def _offloaded(call: ast.Call) -> ast.expr | None:
    """The function an offload such as `asyncio.to_thread(fn, ...)` runs."""
    name = _call_name(call)
    position = OFFLOADS.get(name or "")
    if position is None or len(call.args) <= position:
        return None
    return call.args[position]


BROAD_EXCEPTIONS = frozenset({"Exception", "BaseException", "HTTPException"})


def _swallows_errors(node: ast.AST) -> bool:
    """Whether `node` is a `try` with a handler that catches any HTTP error and never raises."""
    if not isinstance(node, (ast.Try, ast.TryStar)):
        return False
    for handler in node.handlers:
        caught = (
            handler.type.elts if isinstance(handler.type, ast.Tuple) else [handler.type]
        )
        broad = handler.type is None or any(
            (getattr(t, "id", None) or getattr(t, "attr", None)) in BROAD_EXCEPTIONS
            for t in caught
        )
        if broad and not any(isinstance(n, ast.Raise) for n in ast.walk(handler)):
            return True
    return False


def _returns_exceptions(node: ast.AST) -> bool:
    """Whether `node` is an `asyncio.gather(...)` that returns errors instead of raising them."""
    if not isinstance(node, ast.Call):
        return False
    name = _call_name(node)
    return name == "gather" and any(
        kw.arg == "return_exceptions"
        and isinstance(kw.value, ast.Constant)
        and kw.value.value is True
        for kw in node.keywords
    )


def _body_nodes(fn: ast.AST, module: str) -> list[ast.AST]:
    """Every node of a function except its decorators and the code whose errors never reach the caller."""
    mod = load(module)
    ignored = mod.ignored if mod else set()
    roots: list[ast.AST] = (
        [fn.args, *fn.body]
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
        else [fn]
    )
    nodes: list[ast.AST] = []
    while roots:
        node = roots.pop()
        if getattr(node, "lineno", None) in ignored or _returns_exceptions(node):
            continue
        nodes.append(node)
        if _swallows_errors(node):
            # Only a response the body returns can still reach the caller.
            nodes.extend(
                n
                for stmt in node.body  # type: ignore[attr-defined]
                for n in ast.walk(stmt)
                if isinstance(n, ast.Call) and _call_name(n) in RESPONSE_CLASSES
            )
            roots.extend(
                [*node.handlers, *node.orelse, *node.finalbody]  # type: ignore[attr-defined]
            )
            continue
        roots.extend(ast.iter_child_nodes(node))
    return nodes


_memo: dict[Symbol, frozenset[int]] = {}
# The parameters of each function whose value becomes a raised or returned status.
_forwarded: dict[Symbol, frozenset[str]] = {}


def _argument(call: ast.Call, callee: Symbol, param: str) -> ast.expr | None:
    """The expression `call` passes to the callee's parameter `param`."""
    for kw in call.keywords:
        if kw.arg == param:
            return kw.value
    located = _function_node(callee)
    names = _param_names(located[0]) if located else []
    if located and located[1] is not None and names[:1] in (["self"], ["cls"]):
        names = names[1:]
    index = names.index(param) if param in names else len(call.args)
    return call.args[index] if index < len(call.args) else None


def _dependency(node: ast.Call) -> ast.expr | None:
    """The callable a `Depends(...)` or `Security(...)` call injects."""
    name = _call_name(node)
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
        forwarded: set[str] = set()
        if located:
            fn, owner = located

            def add(codes: Codes) -> None:
                found.update(codes.codes)
                forwarded.update(codes.params)
                if codes.unreadable:
                    found.add(UNREADABLE_STATUS)

            for node in _body_nodes(fn, module):
                if isinstance(node, ast.Call):
                    status_expr = _status_expr(node, module, owner)
                    if status_expr is not None:
                        add(_codes(status_expr, module, fn))
                        continue
                    offloaded = _offloaded(node)
                    target = _resolve_expr(module, owner, offloaded or node.func)
                    if target and target[0] != "module":
                        found |= statuses(target, stack)
                    if target and target[0] == "func" and offloaded is None:
                        for param in _forwarded.get(target, frozenset()):
                            arg = _argument(node, target, param)
                            if arg is not None:
                                add(_codes(arg, module, fn))
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
            mod = load(module)
            for line, codes in (mod.declared if mod else {}).items():
                if fn.lineno <= line <= (fn.end_lineno or fn.lineno):  # type: ignore[attr-defined]
                    found |= codes
        _forwarded[sym] = frozenset(forwarded)
    result = frozenset(c for c in found if c >= 400 or c == UNREADABLE_STATUS)
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
        if not route.include_in_schema:
            continue
        endpoint = inspect.unwrap(route.endpoint)
        documented = {int(code) for code in route.responses}
        # FastAPI documents the validation 422 only for a route that takes input.
        if get_flat_params(route.dependant) or route.body_field:
            documented.add(422)
        raised = statuses(("func", endpoint.__module__, endpoint.__name__))
        missing = raised - documented
        if missing:
            key = f"{endpoint.__module__}:{endpoint.__name__}"
            gaps.setdefault(key, set()).update(missing)
    return {key: sorted(codes) for key, codes in sorted(gaps.items())}


def stale(routes: Iterable[Any]) -> dict[str, list[int]]:
    """Map each route's `module:function` to the error statuses its `responses` lists but it cannot raise."""
    scope_defaults = {code: alone for code, (alone, _) in SCOPE_ERRORS.items()}
    gaps: dict[str, set[int]] = {}
    for route in api_routes(routes):
        if not route.include_in_schema:
            continue
        endpoint = inspect.unwrap(route.endpoint)
        raised = statuses(("func", endpoint.__module__, endpoint.__name__))
        if UNREADABLE_STATUS in raised:
            continue
        takes_input = bool(get_flat_params(route.dependant) or route.body_field)
        for code, entry in route.responses.items():
            code = int(code)
            if code < 400 or code in raised or (code == 422 and takes_input):
                continue
            # The scope guard's own 401 and 403, with no reason of the route's added.
            if entry.get("description") == scope_defaults.get(code):
                continue
            key = f"{endpoint.__module__}:{endpoint.__name__}"
            gaps.setdefault(key, set()).add(code)
    return {key: sorted(codes) for key, codes in sorted(gaps.items())}


def main() -> int:
    from main import app  # noqa: PLC0415

    for key, codes in undocumented(app.routes).items():
        print("undocumented", key, codes)
    for key, codes in stale(app.routes).items():
        print("stale", key, codes)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
