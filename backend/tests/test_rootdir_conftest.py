import importlib.util
from pathlib import Path

# Loaded by path: under a full run `conftest` resolves to whichever one pytest cached first.
_spec = importlib.util.spec_from_file_location(
    "rootdir_conftest", Path(__file__).resolve().parents[1] / "conftest.py"
)
assert _spec and _spec.loader
_rootdir_conftest = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_rootdir_conftest)
worktree_tag = _rootdir_conftest.worktree_tag


def test_worktree_tag_names_a_linked_worktree(tmp_path: Path) -> None:
    worktree = tmp_path / "resilient-imagining-clover"
    (worktree / "backend").mkdir(parents=True)
    (worktree / ".git").write_text("gitdir: /repo/.git/worktrees/x\n")

    assert worktree_tag(worktree / "backend").startswith("resilient-imagining-clover_")


def test_worktree_tag_is_empty_in_the_main_checkout(tmp_path: Path) -> None:
    (tmp_path / ".git").mkdir()
    (tmp_path / "backend").mkdir()

    assert worktree_tag(tmp_path / "backend") == ""


def test_worktree_tag_is_empty_outside_a_repository(tmp_path: Path) -> None:
    assert worktree_tag(tmp_path) == ""


def test_worktree_tag_fits_a_database_name(tmp_path: Path) -> None:
    worktree = tmp_path / ("w" * 80)
    worktree.mkdir()
    (worktree / ".git").write_text("gitdir: /repo/.git/worktrees/x\n")

    assert len(worktree_tag(worktree)) == 40


def test_worktree_tag_separates_names_that_sanitize_alike(tmp_path: Path) -> None:
    for name in ("feature-auth", "feature_auth"):
        (tmp_path / name).mkdir()
        (tmp_path / name / ".git").write_text("gitdir: /repo/.git/worktrees/x\n")

    assert worktree_tag(tmp_path / "feature-auth") != worktree_tag(
        tmp_path / "feature_auth"
    )


def test_worktree_tag_separates_names_that_truncate_alike(tmp_path: Path) -> None:
    for suffix in ("a", "b"):
        worktree = tmp_path / ("w" * 50 + suffix)
        worktree.mkdir()
        (worktree / ".git").write_text("gitdir: /repo/.git/worktrees/x\n")

    assert worktree_tag(tmp_path / ("w" * 50 + "a")) != worktree_tag(
        tmp_path / ("w" * 50 + "b")
    )
