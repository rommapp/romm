#!/usr/bin/env python3
"""Find the prose in source files and check it for clipped sentences."""

import argparse
import ast
import io
import json
import re
import subprocess  # nosec B404 - runs only `git diff` with a fixed argv
import sys
import tokenize
from collections.abc import Iterable, Iterator
from dataclasses import asdict, dataclass
from pathlib import Path

# Keyword arguments whose string value is reader-facing text.
TEXT_KEYWORDS = frozenset({"description", "detail", "summary", "help"})
LOG_METHODS = frozenset({"debug", "info", "warning", "error", "exception", "critical"})
SUFFIXES = frozenset({".py", ".ts", ".vue", ".js", ".mts", ".json"})
# Comments that are tool syntax, not prose.
DIRECTIVE = re.compile(
    r"^(noqa|type:|pragma|fmt:|isort:|nosec|pylint:|mypy:|ruff:|eslint|prettier-ignore|"
    r"@ts-|istanbul|c8 |v8 |trunk-ignore|!)"
)
LOCALE_GLOB = "frontend/src/locales/en_US/"


@dataclass(frozen=True)
class Prose:
    path: str
    line: int
    end_line: int
    kind: str
    text: str


@dataclass(frozen=True)
class Rule:
    code: str
    pattern: re.Pattern[str]
    message: str


RULES = (
    Rule(
        "else-chain",
        re.compile(r",\s+else\s+(the|its|a|an|it|to|on|for|from)\b"),
        "Clipped 'X, else Y'. Write 'or else', 'otherwise', or a second sentence.",
    ),
    Rule(
        "clipped-conditional",
        re.compile(
            r"(?:^|[.;:]\s+)(Unset|Left out|Omitted|Absent|Missing|Empty|Null|"
            r"Off|Set|Given|Passed),\s+(the|it|its|a|an|every|each|no|this|that|"
            r"they|we|you)\b"
        ),
        "Clipped conditional. Write 'If left out, ...' or 'When it is empty, ...'.",
    ),
    Rule(
        "internal-id",
        re.compile(r"\binternal id\b", re.IGNORECASE),
        "Write 'The ID of the <thing>.' instead of '<Thing> internal id.'",
    ),
)


def _python_units(path: str, source: str) -> Iterator[Prose]:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return
    raised = {id(n.exc) for n in ast.walk(tree) if isinstance(n, ast.Raise)}
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            if isinstance(node.value.value, str):
                yield Prose(
                    path,
                    node.lineno,
                    node.end_lineno or node.lineno,
                    "docstring",
                    node.value.value,
                )
        elif isinstance(node, ast.Call):
            yield from _message_unit(path, node, raised)
            for kw in node.keywords:
                if kw.arg not in TEXT_KEYWORDS:
                    continue
                text = _literal_text(kw.value)
                if text:
                    yield Prose(
                        path,
                        kw.value.lineno,
                        kw.value.end_lineno or kw.value.lineno,
                        kw.arg,
                        text,
                    )
    yield from _merge_comments(path, _python_comments(source))


def _message_unit(path: str, call: ast.Call, raised: set[int]) -> Iterator[Prose]:
    """Yield the positional message of a raised exception or a logger call."""
    if id(call) in raised:
        kind = "error"
    elif isinstance(call.func, ast.Attribute) and call.func.attr in LOG_METHODS:
        kind = "log"
    else:
        return
    text = _literal_text(call.args[0]) if call.args else ""
    if text:
        arg = call.args[0]
        yield Prose(path, arg.lineno, arg.end_lineno or arg.lineno, kind, text)


def _literal_text(node: ast.expr) -> str:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(
            (
                v.value
                if isinstance(v, ast.Constant) and isinstance(v.value, str)
                else "{}"
            )
            for v in node.values
        )
    return ""


def _python_comments(source: str) -> Iterator[tuple[int, int, str]]:
    try:
        for tok in tokenize.generate_tokens(io.StringIO(source).readline):
            if tok.type == tokenize.COMMENT:
                yield tok.start[0], tok.start[1], tok.string.lstrip("#").strip()
    except (tokenize.TokenError, SyntaxError):
        return


LINE_COMMENT = re.compile(r"(?:^|\s)//\s?(.*)$")
BLOCK_COMMENT = re.compile(r"/\*\*?([\s\S]*?)\*/|<!--([\s\S]*?)-->")


def _script_units(path: str, source: str) -> Iterator[Prose]:
    lines = source.splitlines()
    line_comments = []
    for number, line in enumerate(lines, 1):
        match = LINE_COMMENT.search(line)
        if match:
            line_comments.append((number, match.start(), match.group(1).strip()))
    yield from _merge_comments(path, iter(line_comments))
    for match in BLOCK_COMMENT.finditer(source):
        body = match.group(1) if match.group(1) is not None else match.group(2)
        text = "\n".join(part.strip().lstrip("*").strip() for part in body.splitlines())
        if text.strip() and not DIRECTIVE.match(text.strip()):
            start = source.count("\n", 0, match.start()) + 1
            end = source.count("\n", 0, match.end()) + 1
            yield Prose(path, start, end, "comment", text)


def _merge_comments(
    path: str, comments: Iterator[tuple[int, int, str]]
) -> Iterator[Prose]:
    """Join consecutive line comments at one indent into a single unit."""
    block: list[tuple[int, int, str]] = []
    for comment in comments:
        if DIRECTIVE.match(comment[2]):
            continue
        if block and (comment[0] != block[-1][0] + 1 or comment[1] != block[0][1]):
            yield _comment_block(path, block)
            block = []
        block.append(comment)
    if block:
        yield _comment_block(path, block)


def _comment_block(path: str, block: list[tuple[int, int, str]]) -> Prose:
    # Newlines keep each comment line's offset, so a match maps to its line.
    text = "\n".join(c[2] for c in block)
    return Prose(path, block[0][0], block[-1][0], "comment", text)


def _locale_units(path: str, source: str) -> Iterator[Prose]:
    try:
        data = json.loads(source)
    except json.JSONDecodeError:
        return
    lines = _string_lines(source)
    for key, value in _flatten(data):
        number = lines.get(key, 1)
        yield Prose(path, number, number, f"locale:{key}", value)


JSON_TOKEN = re.compile(r'"(?:[^"\\]|\\.)*"|[{}\[\],]')
JSON_COLON = re.compile(r"\s*:")


def _string_lines(source: str) -> dict[str, int]:
    """Map each dotted key with a string value to the line that holds the value."""
    found: dict[str, int] = {}
    stack: list[str | None] = []
    key: str | None = None
    line, last = 1, 0
    for match in JSON_TOKEN.finditer(source):
        line += source.count("\n", last, match.start())
        last = match.start()
        piece = match.group()
        if piece in ("{", "["):
            stack.append(key)
            key = None
        elif piece in ("}", "]"):
            if stack:
                stack.pop()
            key = None
        elif piece == ",":
            key = None
        elif JSON_COLON.match(source, match.end()):
            key = json.loads(piece)
        elif key is not None:
            found[".".join([k for k in stack if k is not None] + [key])] = line
    return found


def _flatten(data: object, prefix: str = "") -> Iterator[tuple[str, str]]:
    if isinstance(data, dict):
        for key, value in data.items():
            yield from _flatten(value, f"{prefix}{key}.")
    elif isinstance(data, str):
        yield prefix.rstrip("."), data


def units(path: Path) -> Iterator[Prose]:
    source = path.read_text(encoding="utf-8", errors="ignore")
    name = path.as_posix()
    if path.suffix == ".py":
        yield from _python_units(name, source)
    elif path.suffix in {".ts", ".vue", ".js", ".mts"}:
        yield from _script_units(name, source)
    elif path.suffix == ".json" and LOCALE_GLOB in name:
        yield from _locale_units(name, source)


def added_lines(base: str) -> dict[str, set[int]]:
    """Map each file to the line numbers that `git diff <base>` adds to it."""
    diff = subprocess.run(  # nosec B603 B607 - git from PATH, no shell
        ["git", "diff", "-U0", "--no-color", base],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    added: dict[str, set[int]] = {}
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else ""
        elif line.startswith("@@") and current:
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                start, count = int(match.group(1)), int(match.group(2) or 1)
                added.setdefault(current, set()).update(range(start, start + count))
    return added


def violations(unit: Prose) -> Iterator[tuple[Rule, int]]:
    for rule in RULES:
        for match in rule.pattern.finditer(unit.text):
            # Group 1 is the flagged word; the match may start on the line before.
            start = match.start(1) if match.groups() else match.start()
            offset = unit.text.count("\n", 0, start)
            yield rule, unit.line + offset


def _files(paths: Iterable[str]) -> Iterator[Path]:
    for name in paths:
        path = Path(name)
        if path.is_dir():
            yield from sorted(
                p for p in path.rglob("*") if p.suffix in SUFFIXES and p.is_file()
            )
        elif path.is_file():
            yield path


def _select(paths: Iterable[str], base: str | None) -> Iterator[Prose]:
    touched = added_lines(base) if base else None
    candidates = list(touched) if touched is not None and not paths else list(paths)
    for path in _files(candidates):
        name = path.as_posix()
        for unit in units(path):
            if touched is None or any(
                n in touched.get(name, ()) for n in range(unit.line, unit.end_line + 1)
            ):
                yield unit


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("mode", choices=("extract", "check"))
    parser.add_argument("paths", nargs="*")
    parser.add_argument(
        "--diff",
        metavar="BASE",
        help="Only units on lines added since BASE, such as `origin/master...`.",
    )
    args = parser.parse_intermixed_args(argv)

    found = False
    for unit in _select(args.paths, args.diff):
        if args.mode == "extract":
            print(json.dumps(asdict(unit), ensure_ascii=False))
            continue
        for rule, line in violations(unit):
            found = True
            print(f"{unit.path}:{line}:1: [{rule.code}] {rule.message}")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
