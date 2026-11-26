from pathlib import Path

import pytest
from tools.prose_check import Prose, main, units, violations

PYTHON_SOURCE = '''"""Module docstring."""

from fastapi import Query

# Two comment lines that
# form one sentence.
LIMIT = Query(description="The ID of the rom.")  # noqa: E501


def handler():
    raise ValueError(detail=f"No rom {LIMIT}.")
'''

SCRIPT_SOURCE = """// A line comment.
const url = "https://example.com"; // Trailing comment.
/** A block
 * comment. */
// eslint-disable-next-line no-console
"""


def _codes(text: str) -> list[str]:
    return [rule.code for rule, _ in violations(Prose("x.py", 1, 1, "comment", text))]


def test_python_units_cover_docstrings_descriptions_details_and_comments(
    tmp_path: Path,
) -> None:
    path = tmp_path / "module.py"
    path.write_text(PYTHON_SOURCE)

    found = {(unit.kind, unit.text) for unit in units(path)}

    assert found == {
        ("docstring", "Module docstring."),
        ("comment", "Two comment lines that\nform one sentence."),
        ("description", "The ID of the rom."),
        ("detail", "No rom {}."),
    }


def test_script_units_skip_urls_and_directives(tmp_path: Path) -> None:
    path = tmp_path / "module.ts"
    path.write_text(SCRIPT_SOURCE)

    found = sorted(unit.text for unit in units(path))

    assert found == ["A block\ncomment.", "A line comment.", "Trailing comment."]


def test_locale_units_read_en_us_values_only(tmp_path: Path) -> None:
    en_us = tmp_path / "frontend/src/locales/en_US"
    en_us.mkdir(parents=True)
    (en_us / "rom.json").write_text(
        '{\n  "title": "Title",\n  "nested": {"hint": "A hint."}\n}\n'
    )
    fr_fr = tmp_path / "frontend/src/locales/fr_FR"
    fr_fr.mkdir(parents=True)
    (fr_fr / "rom.json").write_text('{"title": "Titre"}')

    found = [(u.kind, u.line) for u in units(en_us / "rom.json")]

    assert found == [("locale:title", 2), ("locale:nested.hint", 3)]
    assert list(units(fr_fr / "rom.json")) == []


@pytest.mark.parametrize(
    ("text", "codes"),
    [
        ("The device to clear, else the client token's.", ["else-chain"]),
        ("Left out, the server picks one.", ["clipped-conditional"]),
        ("The ID of the rom. Unset, every rom matches.", ["clipped-conditional"]),
        ("Rom internal id.", ["internal-id"]),
        ("Absent, empty and over-long hashes all mean unknown.", []),
        ("If left out, the server picks one, or else the first.", []),
        ("The ID of the rom.", []),
    ],
)
def test_rules(text: str, codes: list[str]) -> None:
    assert _codes(text) == codes


def test_check_reports_path_line_and_rule(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "module.py"
    path.write_text("X = 1\n\n# Fine.\n# Left out, the default\n# applies.\n")

    status = main(["check", str(path)])

    assert status == 1
    assert capsys.readouterr().out == (
        f"{path.as_posix()}:4:1: [clipped-conditional] "
        "Clipped conditional. Write 'If left out, ...' or 'When it is empty, ...'.\n"
    )


def test_python_units_cover_raised_and_logged_messages(tmp_path: Path) -> None:
    path = tmp_path / "module.py"
    path.write_text(
        'def f(log):\n    log.error("Scan failed.")\n'
        '    print("Not prose.")\n    raise ValueError(f"No rom {log}.")\n'
    )

    found = {(unit.kind, unit.line, unit.text) for unit in units(path)}

    assert found == {("log", 2, "Scan failed."), ("error", 4, "No rom {}.")}


def test_locale_units_point_to_their_own_key(tmp_path: Path) -> None:
    en_us = tmp_path / "frontend/src/locales/en_US"
    en_us.mkdir(parents=True)
    (en_us / "rom.json").write_text(
        '{\n  "a": {\n    "hint": "A."\n  },\n  "b": {\n    "hint": "B."\n  }\n}\n'
    )

    found = [(u.kind, u.line) for u in units(en_us / "rom.json")]

    assert found == [("locale:a.hint", 3), ("locale:b.hint", 6)]


def test_extract_expands_directories(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "module.py").write_text("# A comment.\n")
    (tmp_path / "pkg" / "notes.txt").write_text("# Not source.\n")

    assert main(["extract", str(tmp_path)]) == 0
    assert '"text": "A comment."' in capsys.readouterr().out


def test_paths_may_follow_diff(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    path = tmp_path / "module.py"
    path.write_text("# Left out, the default applies.\n")
    monkeypatch.setattr(
        "tools.prose_check.added_lines", lambda base: {path.as_posix(): {1}}
    )

    assert main(["check", "--diff", "origin/master...", str(path)]) == 1


def test_check_passes_clean_files(tmp_path: Path) -> None:
    path = tmp_path / "module.py"
    path.write_text("# If left out, the default applies.\n")

    assert main(["check", str(path)]) == 0
