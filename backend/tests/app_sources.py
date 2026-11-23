import ast
from collections.abc import Iterator
from pathlib import Path

BACKEND_ROOT = Path(__file__).parents[1]


def app_sources() -> Iterator[tuple[Path, ast.Module]]:
    """Each app module under backend/, as its relative path and parsed tree."""
    for path in BACKEND_ROOT.rglob("*.py"):
        relative = path.relative_to(BACKEND_ROOT)
        if relative.parts[0] in {"tests", "alembic"}:
            continue
        yield relative, ast.parse(path.read_text(), filename=str(path))
