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
# Response classes a route can return instead of raising. Their status reaches the
# client.
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
# response. A route that reaches one fails the check until that line declares its
# statuses with `RAISES_MARKER`.
UNREADABLE_STATUS = 0
# Marks code whose errors never reach the client. Put it at the end of the line, or
# on the line above, with the reason after it.
IGNORE_MARKER = "# route-errors: ignore"
# Declares the statuses a line raises when the analyzer cannot follow or read them,
# such as `# route-errors: raises 409, 423`. It replaces what the analyzer reads there.
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


def _params(fn: ast.AST | None) -> list[ast.arg]:
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return []
    return [*fn.args.posonlyargs, *fn.args.args, *fn.args.kwonlyargs]


def _param_names(fn: ast.AST | None) -> list[str]:
    return [param.arg for param in _params(fn)]


def _local_bindings(fn: ast.AST | None, name: str) -> tuple[list[ast.expr], bool]:
    """The values plain assignments give to the local `name` in `fn`, and whether any other statement binds it."""
    if fn is None:
        return [], False
    values: list[ast.expr] = []
    plain: set[int] = set()
    for node in ast.walk(fn):
        targets: list[ast.expr]
        value: ast.expr | None
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name) and target.id == name:
                plain.add(id(target))
                if value is not None:
                    values.append(value)
    # Tuple unpacking, `+=`, `for`, `with ... as` or `:=` give a value the
    # analyzer does not read.
    rebound = any(
        isinstance(node, ast.Name)
        and node.id == name
        and isinstance(node.ctx, ast.Store)
        and id(node) not in plain
        for node in ast.walk(fn)
    )
    return values, rebound


def _default(callee: Symbol, param: str) -> ast.expr | None:
    """The default value of the callee's parameter `param`."""
    located = _function_node(callee)
    fn = located[0] if located else None
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return None
    positional = [*fn.args.posonlyargs, *fn.args.args]
    defaults = {
        arg.arg: value
        for arg, value in zip(
            positional[len(positional) - len(fn.args.defaults) :],
            fn.args.defaults,
            strict=False,
        )
    }
    for arg, value in zip(fn.args.kwonlyargs, fn.args.kw_defaults, strict=False):
        if value is not None:
            defaults[arg.arg] = value
    return defaults.get(param)


def _module_dict(module: str, expr: ast.expr) -> ast.Dict | None:
    """The literal dict a module-level name holds, such as a map of errors to statuses."""
    if not isinstance(expr, ast.Name):
        return None
    sym = resolve(module, expr.id)
    mod = load(sym[1]) if sym and sym[0] == "value" else None
    value = mod.assigns.get(sym[2]) if mod and sym else None
    return value if isinstance(value, ast.Dict) else None


def _codes(
    expr: ast.expr | None, module: str, fn: ast.AST | None, depth: int = 0
) -> Codes:
    """The statuses a `status_code` expression in `fn`, or at module level when `fn` is None, can take."""
    if expr is None or depth > 10:
        return Codes(unreadable=True)

    def union(exprs: Iterable[ast.expr]) -> Codes:
        found = Codes()
        for value in exprs:
            found |= _codes(value, module, fn, depth + 1)
        return found

    code = _status(expr)
    if code is not None:
        return Codes(frozenset({code}))
    # A `None` default stands for a status the callee picks itself.
    if isinstance(expr, ast.Constant) and expr.value is None:
        return Codes()
    if isinstance(expr, ast.IfExp):
        return union([expr.body, expr.orelse])
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
        return union([*lookup.values, *([default] if default else [])])
    if isinstance(expr, ast.Name):
        is_param = expr.id in _param_names(fn)
        values, rebound = _local_bindings(fn, expr.id)
        if is_param or values or rebound:
            return Codes(
                params=frozenset({expr.id}) if is_param else frozenset(),
                unreadable=rebound,
            ) | union(values)
        sym = resolve(module, expr.id)
        mod = load(sym[1]) if sym and sym[0] == "value" else None
        if mod and sym:
            return _codes(mod.assigns[sym[2]], sym[1], None, depth + 1)
    return Codes(unreadable=True)


def _subclasses_http_exception(module: str, owner: str | None) -> bool:
    mod = load(module)
    cls = mod.classes.get(owner) if mod and owner else None
    return cls is not None and any(
        getattr(base, "id", getattr(base, "attr", None)) == "HTTPException"
        for base in cls.bases
    )


def _subclasses_response(cls: Symbol, depth: int = 0) -> bool:
    """Whether a class derives from one of `RESPONSE_CLASSES`."""
    mod = load(cls[1])
    node = mod.classes.get(cls[2]) if mod else None
    if node is None or depth > 10:
        return False
    for base in node.bases:
        if (
            getattr(base, "id", None) or getattr(base, "attr", None)
        ) in RESPONSE_CLASSES:
            return True
        sym = _resolve_expr(cls[1], None, base)
        if sym and sym[0] == "class" and _subclasses_response(sym, depth + 1):
            return True
    return False


def _builds_response(call: ast.Call, module: str, owner: str | None = None) -> bool:
    """Whether `call` constructs a response, including one of the codebase's own subclasses."""
    if _call_name(call) in RESPONSE_CLASSES:
        return True
    target = _resolve_expr(module, owner, call.func) if module else None
    return bool(target and target[0] == "class" and _subclasses_response(target))


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
    position: int | None
    if name == "HTTPException" or is_super_init:
        position = 0
    elif name in RESPONSE_CLASSES:
        position = 1
    elif _builds_response(call, module, owner):
        # A subclass's own signature is unknown, so only `status_code=` is read.
        position = None
    else:
        return None
    for kw in call.keywords:
        if kw.arg == "status_code":
            return kw.value
    if position is None or len(call.args) <= position:
        return None
    return call.args[position]


def _http_exception_status(call: ast.Call) -> int | None:
    """The status of a module-level `HTTPException(...)` instance."""
    if _call_name(call) != "HTTPException":
        return None
    return _status(_status_expr(call))


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


# Calls that run a function passed as an argument and re-raise its errors, mapped
# to the position of that argument.
OFFLOADS = {"to_thread": 0, "run_in_threadpool": 0, "run_sync": 0, "run_in_executor": 1}


def _offloaded(call: ast.Call) -> ast.Call | None:
    """The call an offload such as `asyncio.to_thread(fn, *args)` makes, as `fn(*args)`."""
    name = _call_name(call)
    position = OFFLOADS.get(name or "")
    if position is None or len(call.args) <= position:
        return None
    return ast.Call(
        func=call.args[position],
        args=call.args[position + 1 :],
        keywords=call.keywords,
    )


BROAD_EXCEPTIONS = frozenset({"Exception", "BaseException", "HTTPException"})


def _swallows_errors(node: ast.AST) -> bool:
    """Whether `node` is a `try` whose first handler to catch an HTTP error never raises."""
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
        if broad:
            return not any(isinstance(n, ast.Raise) for n in ast.walk(handler))
    return False


def _sets_status(node: ast.AST, module: str) -> bool:
    """Whether `node` builds a response or sets a `status_code`, which a swallowing `try` lets through."""
    if isinstance(node, ast.Assign):
        return any(
            isinstance(target, ast.Attribute) and target.attr == "status_code"
            for target in node.targets
        )
    return isinstance(node, ast.Call) and _builds_response(node, module)


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
    # Each node to visit carries whether it sits in the body of a `try` that swallows errors.
    roots: list[tuple[ast.AST, bool]] = [
        (node, False)
        for node in (
            [fn.args, *fn.body]
            if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef))
            else [fn]
        )
    ]
    nodes: list[ast.AST] = []
    while roots:
        node, swallowed = roots.pop()
        if getattr(node, "lineno", None) in ignored or _returns_exceptions(node):
            continue
        # Only a status the swallowed code returns can still reach the caller.
        if not swallowed or _sets_status(node, module):
            nodes.append(node)
        if not swallowed and _swallows_errors(node):
            roots.extend((stmt, True) for stmt in node.body)  # type: ignore[attr-defined]
            roots.extend(
                (child, False)
                for child in [*node.handlers, *node.orelse, *node.finalbody]  # type: ignore[attr-defined]
            )
            continue
        roots.extend((child, swallowed) for child in ast.iter_child_nodes(node))
    return nodes


_memo: dict[Symbol, frozenset[int]] = {}
# For each function, the parameters whose value becomes a raised or returned status.
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


def _passed(
    call: ast.Call, callee: Symbol, param: str, module: str, fn: ast.AST
) -> Codes:
    """The statuses that `call`, made in `fn`, passes to the callee's parameter `param`."""
    arg = _argument(call, callee, param)
    if arg is not None:
        return _codes(arg, module, fn)
    if any(isinstance(a, ast.Starred) for a in call.args) or any(
        kw.arg is None for kw in call.keywords
    ):
        return Codes(unreadable=True)
    default = _default(callee, param)
    # A default is evaluated where the callee is defined.
    return _codes(default, callee[1], None) if default is not None else Codes()


def _injected(target: Symbol, stack: frozenset[Symbol]) -> frozenset[int]:
    """The statuses of an endpoint or dependency. FastAPI fills its parameters from the request, so a status read from one is unreadable."""
    found = statuses(target, stack)
    if _forwarded.get(target):
        return found | {UNREADABLE_STATUS}
    return found


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
    return [
        node
        for param in _params(fn)
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
                found |= _injected(target, stack)
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
                    call = _offloaded(node) or node
                    target = _resolve_expr(module, owner, call.func)
                    if target and target[0] != "module":
                        found |= statuses(target, stack)
                    callee = (
                        _method(target, "__init__")
                        if target and target[0] == "class"
                        else target
                    )
                    if callee and callee[0] == "func":
                        for param in _forwarded.get(callee, frozenset()):
                            add(_passed(call, callee, param, module, fn))
                    dependency = _dependency(node)
                    target = (
                        _resolve_expr(module, owner, dependency) if dependency else None
                    )
                    if target and target[0] == "func":
                        found |= _injected(target, stack)
                elif isinstance(node, ast.Assign) and _sets_status(node, module):
                    add(_codes(node.value, module, fn))
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


def _endpoint(route: APIRoute) -> tuple[str, frozenset[int]]:
    """A route's `module:function` key and the statuses its endpoint can raise."""
    endpoint = inspect.unwrap(route.endpoint)
    sym = ("func", endpoint.__module__, endpoint.__name__)
    return f"{endpoint.__module__}:{endpoint.__name__}", _injected(sym, frozenset())


def _takes_input(route: APIRoute) -> bool:
    """Whether FastAPI validates input for the route, and so documents its 422."""
    return bool(get_flat_params(route.dependant) or route.body_field)


def _documents(responses: dict[int | str, Any], code: int) -> bool:
    """Whether `responses` describes `code`, by itself or through `4XX` or `default`."""
    keys = {str(key).upper() for key in responses}
    return code != UNREADABLE_STATUS and (
        str(code) in keys or f"{code // 100}XX" in keys or "DEFAULT" in keys
    )


def undocumented(routes: Iterable[Any]) -> dict[str, list[int]]:
    """Map each route's `module:function` to the statuses it raises that its `responses` leaves out."""
    gaps: dict[str, set[int]] = {}
    for route in api_routes(routes):
        if not route.include_in_schema:
            continue
        key, raised = _endpoint(route)
        takes_input = _takes_input(route)
        missing = {
            code
            for code in raised
            if not _documents(route.responses, code)
            and not (code == 422 and takes_input)
        }
        if missing:
            gaps.setdefault(key, set()).update(missing)
    return {key: sorted(codes) for key, codes in sorted(gaps.items())}


def stale(routes: Iterable[Any]) -> dict[str, list[int]]:
    """Map each route's `module:function` to the error statuses its `responses` lists but it cannot raise."""
    scope_defaults = {code: alone for code, (alone, _) in SCOPE_ERRORS.items()}
    gaps: dict[str, set[int]] = {}
    for route in api_routes(routes):
        if not route.include_in_schema:
            continue
        key, raised = _endpoint(route)
        if UNREADABLE_STATUS in raised:
            continue
        takes_input = _takes_input(route)
        for documented, entry in route.responses.items():
            # A range such as `4XX`, or `default`, names no single status.
            if not str(documented).isdigit():
                continue
            code = int(documented)
            if code < 400 or code in raised or (code == 422 and takes_input):
                continue
            # The scope guard documents its own 401 and 403. Skip them unless the
            # route added a reason to the description.
            if code in scope_defaults and entry.get("description") == (
                scope_defaults[code]
            ):
                continue
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
