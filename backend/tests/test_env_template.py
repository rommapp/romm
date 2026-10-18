"""Guards that env.template, which generates the docs' env var reference, lists every setting."""

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
CONFIG_MODULE = REPO_ROOT / "backend" / "config" / "__init__.py"
ENV_TEMPLATE = REPO_ROOT / "env.template"

ENV_READERS = {"_get_env", "_get_env_list", "_get_env_set"}
# Set by pytest itself, not by users.
NOT_USER_SETTINGS = {"PYTEST_VERSION"}


def _env_vars_read_by_config() -> set[str]:
    names = set()
    for node in ast.walk(ast.parse(CONFIG_MODULE.read_text())):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in ENV_READERS
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ):
            names.add(node.args[0].value)
    return names - NOT_USER_SETTINGS


def _env_vars_in_template() -> set[str]:
    names = set()
    for line in ENV_TEMPLATE.read_text().splitlines():
        key, sep, _ = line.lstrip("# ").partition("=")
        if sep and key.isupper():
            names.add(key)
    return names


def test_env_template_lists_every_env_var_the_config_reads() -> None:
    missing = _env_vars_read_by_config() - _env_vars_in_template()
    assert not missing, f"env.template is missing {sorted(missing)}"
