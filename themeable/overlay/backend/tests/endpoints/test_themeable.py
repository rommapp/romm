import asyncio
import io
import json
import shutil
import time
import zipfile
from pathlib import Path

import endpoints.themeable as themeable
import pytest
from fastapi import status
from tests._zipfile_shim import reload_zipfile

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
    task = asyncio.create_task(themeable._run_compiler(["--select", "ember"]))
    await asyncio.sleep(1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    _assert_stopped_and_clean(slow_compiler, themes)


def test_branding_requires_auth(client):
    response = client.get("/api/themeable/branding")
    assert response.status_code == status.HTTP_401_UNAUTHORIZED


def test_branding_is_admin_only(client, editor_access_token):
    response = client.get("/api/themeable/branding", headers=_auth(editor_access_token))
    assert response.status_code == status.HTTP_403_FORBIDDEN
    response = client.put(
        "/api/themeable/branding",
        json={"theme": "none"},
        headers=_auth(editor_access_token),
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN
    for method, url in (
        ("post", "/api/themeable/packs"),
        ("patch", "/api/themeable/packs/ember"),
        ("delete", "/api/themeable/packs/ember"),
        ("post", "/api/themeable/packs/built-ins/restore"),
    ):
        kwargs = {"json": {"name": "x"}} if method == "patch" else {}
        response = getattr(client, method)(
            url, headers=_auth(editor_access_token), **kwargs
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN, url


def test_read_only_tokens_cannot_change_themes(client, access_token):
    response = client.post(
        "/api/client-tokens",
        json={"name": "Read only", "scopes": ["roms.read"]},
        headers=_auth(access_token),
    )
    read_only = response.json()["raw_token"]
    response = client.get("/api/themeable/branding", headers=_auth(read_only))
    assert response.status_code == status.HTTP_200_OK
    for method, url in (
        ("post", "/api/themeable/branding/rescan"),
        ("put", "/api/themeable/branding"),
        ("post", "/api/themeable/packs"),
        ("patch", "/api/themeable/packs/ember"),
        ("delete", "/api/themeable/packs/ember"),
        ("post", "/api/themeable/packs/built-ins/restore"),
    ):
        kwargs = (
            {"json": {"theme": "ember", "name": "x"}}
            if method in ("put", "patch")
            else {}
        )
        response = getattr(client, method)(url, headers=_auth(read_only), **kwargs)
        assert response.status_code == status.HTTP_403_FORBIDDEN, url


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


def test_save_selects_a_pack_and_stores_it_in_the_folder(client, access_token, themes):
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


def test_save_sets_randoms_groups(client, access_token, themes):
    response = client.put(
        "/api/themeable/branding",
        json={"theme": "random", "random": {"stock": True, "built_in": False}},
        headers=_auth(access_token),
    )
    body = response.json()
    assert body["random"]["stock"] is True
    assert body["random"]["built_in"] is False
    assert body["random"]["ids"][0] == "none"
    assert "neon" not in body["random"]["ids"]
    assert "signal" in body["random"]["ids"]
    saved = json.loads((themes / "themeable.json").read_text())
    assert saved["random"] == {"stock": True, "built_in": False, "accessibility": True}
    signal = next(p for p in body["packs"] if p["id"] == "signal")
    assert signal["tags"] == ["accessibility"]


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
    response = client.delete("/api/themeable/packs/Bad_Id", headers=_auth(access_token))
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


def _pack_zip(pack_id: str, name: str, **extra) -> bytes:
    reload_zipfile()
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            f"{pack_id}/theme.json", json.dumps({"id": pack_id, "name": name, **extra})
        )
    return buffer.getvalue()


def _upload(client, token: str, data: bytes, replace: bool = False):
    return client.post(
        "/api/themeable/packs" + ("?replace=true" if replace else ""),
        files={"file": ("pack.zip", data, "application/zip")},
        headers=_auth(token),
    )


def test_upload_installs_a_pack_and_asks_before_replacing(client, access_token, themes):
    response = _upload(client, access_token, _pack_zip("dusk", "Dusk"))
    assert response.status_code == status.HTTP_200_OK
    body = response.json()
    assert body["ok"] is True
    assert body["max_upload_bytes"] == themeable.MAX_UPLOAD_BYTES
    dusk = next(p for p in body["packs"] if p["id"] == "dusk")
    assert (dusk["format"], dusk["name"], dusk["valid"]) == ("zip", "Dusk", True)
    assert sorted(p.name for p in themes.iterdir()) == ["dusk.zip"]

    response = _upload(client, access_token, _pack_zip("dusk", "Dusk 2"))
    assert response.status_code == status.HTTP_409_CONFLICT
    assert response.json()["detail"]["id"] == "dusk"
    response = _upload(client, access_token, _pack_zip("dusk", "Dusk 2"), replace=True)
    assert next(p for p in response.json()["packs"] if p["id"] == "dusk")["name"] == (
        "Dusk 2"
    )
    assert not list((themeable.RUNTIME_DIR / "uploads").iterdir())


def test_upload_refuses_bad_packs_with_their_problems(client, access_token, themes):
    response = _upload(client, access_token, _pack_zip("neon", "My neon"))
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "built-in" in response.json()["detail"]["problems"][0]

    bad = _pack_zip("bad", "Bad", extraCss="missing.css")
    response = _upload(client, access_token, bad)
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "extraCss" in " ".join(response.json()["detail"]["problems"])

    response = _upload(client, access_token, b"not a zip")
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    assert "could not be read" in response.json()["detail"]["problems"][0]
    assert not list(themes.iterdir())


def test_upload_over_the_size_cap_is_refused(client, access_token, themes, monkeypatch):
    monkeypatch.setattr(themeable, "MAX_UPLOAD_BYTES", 1024)
    monkeypatch.setattr(themeable, "MULTIPART_OVERHEAD_BYTES", 512)
    response = _upload(client, access_token, b"x" * 4096)
    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
    response = client.post(
        "/api/themeable/packs",
        files={"other": ("pack.zip", b"PK", "application/zip")},
        headers=_auth(access_token),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert not list(themes.iterdir())


def test_rename_and_delete_an_uploaded_pack(client, access_token, themes):
    _upload(client, access_token, _pack_zip("dusk", "Dusk"))
    response = client.patch(
        "/api/themeable/packs/dusk",
        json={"name": "Evening"},
        headers=_auth(access_token),
    )
    assert next(p for p in response.json()["packs"] if p["id"] == "dusk")["name"] == (
        "Evening"
    )
    client.put(
        "/api/themeable/branding", json={"theme": "dusk"}, headers=_auth(access_token)
    )
    response = client.delete("/api/themeable/packs/dusk", headers=_auth(access_token))
    body = response.json()
    assert body["ok"] is True
    assert body["selected"] == "none"
    assert not (themes / "dusk.zip").exists()


def test_built_in_packs_are_hidden_and_restored(client, access_token, themes):
    response = client.delete("/api/themeable/packs/neon", headers=_auth(access_token))
    body = response.json()
    assert body["hidden"] == ["neon"]
    assert all(p["id"] != "neon" for p in body["packs"])
    response = client.patch(
        "/api/themeable/packs/neon",
        json={"name": "Neon Nights"},
        headers=_auth(access_token),
    )
    assert response.json()["ok"] is True
    response = client.patch(
        "/api/themeable/packs/neon", json={"name": None}, headers=_auth(access_token)
    )
    assert response.json()["ok"] is True
    response = client.post(
        "/api/themeable/packs/built-ins/restore", headers=_auth(access_token)
    )
    assert response.json()["hidden"] == []
    assert any(p["id"] == "neon" for p in response.json()["packs"])


def test_romm_default_can_never_be_renamed_or_deleted(client, access_token):
    response = client.patch(
        "/api/themeable/packs/none", json={"name": "X"}, headers=_auth(access_token)
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT
    response = client.delete("/api/themeable/packs/none", headers=_auth(access_token))
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


def test_folder_packs_are_converted_to_archives(client, access_token, themes):
    (themes / "mine").mkdir()
    (themes / "mine" / "theme.json").write_text(
        json.dumps({"id": "mine", "name": "Mine"})
    )
    response = client.post(
        "/api/themeable/branding/rescan", headers=_auth(access_token)
    )
    mine = next(p for p in response.json()["packs"] if p["id"] == "mine")
    assert mine["format"] == "zip"
    assert (themes / "mine.zip").is_file()
    assert (themes / ".converted" / "mine" / "theme.json").is_file()


def test_built_in_packs_are_renamed_and_reset(client, access_token, themes):
    response = client.patch(
        "/api/themeable/packs/neon",
        json={"name": "Neon Nights"},
        headers=_auth(access_token),
    )
    neon = next(p for p in response.json()["packs"] if p["id"] == "neon")
    assert (neon["name"], neon["default_name"]) == ("Neon Nights", "Neon")
    response = client.patch(
        "/api/themeable/packs/neon", json={"name": None}, headers=_auth(access_token)
    )
    neon = next(p for p in response.json()["packs"] if p["id"] == "neon")
    assert (neon["name"], neon["default_name"]) == ("Neon", None)
