import asyncio
import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi import status

import endpoints.themeable as themeable

# The module sits next to backend/ in the repository; tests run the real compiler.
MODULE_HOME = Path(__file__).resolve().parents[3] / "themeable"


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(autouse=True)
def themes(tmp_path, monkeypatch):
    if shutil.which("node") is None or not MODULE_HOME.exists():
        pytest.skip("needs node and the themeable module")
    packs = tmp_path / "themes"
    packs.mkdir()
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("THEMEABLE_PACKS_PATH", str(packs))
    monkeypatch.setenv("THEMEABLE_RUNTIME_DIR", str(runtime))
    monkeypatch.setattr(themeable, "THEMEABLE_HOME", MODULE_HOME)
    monkeypatch.setattr(themeable, "RUNTIME_DIR", runtime)
    monkeypatch.setattr(themeable, "PACKS_PATH", packs)
    return packs


# Stands in for runtime.mjs: takes the lock, stages a selection, ignores SIGTERM and
# would only finish (writing "late") long after the backend gave up on it.
SLOW_COMPILER = """
import { mkdirSync, writeFileSync } from "node:fs";
const runtime = process.env.THEMEABLE_RUNTIME_DIR;
mkdirSync(runtime, { recursive: true });
writeFileSync(`${runtime}/compile.lock`, String(process.pid));
writeFileSync(`${process.env.THEMEABLE_PACKS_PATH}/themeable.json.${process.pid}.tmp`, "{}");
process.on("SIGTERM", () => {});
setTimeout(() => writeFileSync(`${runtime}/late`, "finished"), 4000);
"""


@pytest.fixture
def slow_compiler(tmp_path, monkeypatch):
    home = tmp_path / "slow-home"
    (home / "scripts").mkdir(parents=True)
    (home / "scripts" / "runtime.mjs").write_text(SLOW_COMPILER)
    monkeypatch.setattr(themeable, "THEMEABLE_HOME", home)
    monkeypatch.setattr(themeable, "STOP_GRACE_SECONDS", 0.5)
    return themeable.RUNTIME_DIR


def _assert_stopped_and_clean(runtime: Path, packs: Path) -> None:
    assert not (runtime / "compile.lock").exists()
    assert not list(packs.glob("themeable.json.*.tmp"))
    assert not (packs / "themeable.json").exists()
    time.sleep(4.5)
    assert not (runtime / "late").exists(), "the compiler kept running"


def test_timed_out_save_stops_the_compiler(
    client, access_token, themes, slow_compiler, monkeypatch
):
    monkeypatch.setattr(themeable, "COMPILE_TIMEOUT_SECONDS", 1)
    response = client.put(
        "/api/themeable/branding",
        json={"theme": "ember"},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_504_GATEWAY_TIMEOUT
    assert "nothing was changed" in response.json()["detail"]
    _assert_stopped_and_clean(slow_compiler, themes)


async def test_cancelled_save_stops_the_compiler(themes, slow_compiler):
    task = asyncio.create_task(themeable._run_compiler("ember"))
    await asyncio.sleep(1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    _assert_stopped_and_clean(slow_compiler, themes)


def test_branding_requires_auth(client):
    response = client.get("/api/themeable/branding")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_branding_is_admin_only(client, editor_access_token):
    response = client.get(
        "/api/themeable/branding", headers=_auth(editor_access_token)
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    response = client.put(
        "/api/themeable/branding",
        json={"theme": "none"},
        headers=_auth(editor_access_token),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_lists_built_in_packs_with_stock_look_selected(client, access_token):
    response = client.get("/api/themeable/branding", headers=_auth(access_token))
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["ok"] is True
    assert body["selected"] == "none"
    assert body["effective"] == "none"
    assert body["client"]["stock_id"] == body["selected"]
    assert body["client"]["storage_key"]
    ember = next(p for p in body["packs"] if p["id"] == "ember")
    assert ember["source"] == "built-in"
    assert ember["valid"] is True


def test_save_selects_a_pack_and_stores_it_in_the_folder(
    client, access_token, themes
):
    response = client.put(
        "/api/themeable/branding",
        json={"theme": "ember"},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["effective"] == "ember"
    saved = json.loads((themes / "themeable.json").read_text())
    assert saved["theme"] == "ember"


def test_save_selects_random(client, access_token, themes):
    response = client.put(
        "/api/themeable/branding",
        json={"theme": "random"},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["client"]["random_id"] == "random"
    assert body["client"]["random_cycle_ms"] > 0
    assert body["effective"] == "random"
    saved = json.loads((themes / "themeable.json").read_text())
    assert saved["theme"] == "random"


def test_missing_theme_falls_back_to_the_stock_look(client, access_token):
    response = client.put(
        "/api/themeable/branding",
        json={"theme": "not-installed"},
        headers=_auth(access_token),
    )
    body = response.json()
    assert body["selected"] == "not-installed"
    assert body["effective"] == "none"
    assert any("not installed" in note for note in body["notes"])


def test_broken_folder_pack_is_listed_with_its_errors(client, access_token, themes):
    (themes / "broken").mkdir()
    (themes / "broken" / "theme.json").write_text("{ not json")
    response = client.put(
        "/api/themeable/branding",
        json={"theme": "broken"},
        headers=_auth(access_token),
    )
    body = response.json()
    broken = next(p for p in body["packs"] if p["id"] == "broken")
    assert broken["valid"] is False
    assert broken["errors"]
    assert body["effective"] == "none"


def test_rejects_unsafe_theme_ids(client, access_token):
    response = client.put(
        "/api/themeable/branding",
        json={"theme": "../etc"},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_rescan_picks_up_new_folder_packs(client, access_token, themes):
    client.get("/api/themeable/branding", headers=_auth(access_token))
    (themes / "added").mkdir()
    (themes / "added" / "theme.json").write_text(
        json.dumps({"id": "added", "name": "Added later"})
    )
    response = client.post(
        "/api/themeable/branding/rescan", headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_200_OK
    added = next(p for p in response.json()["packs"] if p["id"] == "added")
    assert added["source"] == "folder"
    assert added["valid"] is True
