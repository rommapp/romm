import io
from collections.abc import Callable
from pathlib import Path

import httpx2
import pytest
from PIL import Image

from handler.auth import oidc_avatar
from handler.auth.oidc_avatar import sync_oidc_avatar
from handler.database import db_user_handler
from handler.filesystem import fs_asset_handler
from models.user import User

PICTURE_URL = "https://idp.example.com/avatars/me.png"


def _png() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), (200, 0, 0)).save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def assets_dir(tmp_path, monkeypatch) -> Path:
    base = Path(tmp_path).resolve()
    monkeypatch.setattr(fs_asset_handler, "base_path", base)
    return base


def _serve(
    monkeypatch, handler: Callable[[httpx2.Request], httpx2.Response]
) -> list[httpx2.Request]:
    requests: list[httpx2.Request] = []

    def record(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return handler(request)

    monkeypatch.setattr(
        oidc_avatar,
        "create_httpx_async_client",
        lambda allowlist: httpx2.AsyncClient(transport=httpx2.MockTransport(record)),
    )
    return requests


def _reload(user: User) -> User:
    reloaded = db_user_handler.get_user(user.id)
    assert reloaded
    return reloaded


async def test_stores_the_picture_as_the_avatar(
    monkeypatch, assets_dir: Path, viewer_user: User
):
    png = _png()
    _serve(monkeypatch, lambda _: httpx2.Response(200, content=png))

    await sync_oidc_avatar(viewer_user, {"picture": PICTURE_URL})

    avatar_path = _reload(viewer_user).avatar_path
    assert avatar_path.endswith("/profile/oidc-avatar.png")
    assert (assets_dir / avatar_path).read_bytes() == png


async def test_keeps_an_uploaded_avatar(monkeypatch, viewer_user: User):
    db_user_handler.update_user(
        viewer_user.id, {"avatar_path": "users/x/profile/avatar.png"}
    )
    requests = _serve(monkeypatch, lambda _: httpx2.Response(200, content=_png()))

    await sync_oidc_avatar(_reload(viewer_user), {"picture": PICTURE_URL})

    assert requests == []
    assert _reload(viewer_user).avatar_path == "users/x/profile/avatar.png"


async def test_replaces_a_previous_oidc_avatar(
    monkeypatch, assets_dir: Path, viewer_user: User
):
    avatar_dir = fs_asset_handler.build_avatar_path(user=viewer_user)
    old_path = f"{avatar_dir}/oidc-avatar.gif"
    (assets_dir / avatar_dir).mkdir(parents=True)
    (assets_dir / old_path).write_bytes(b"old")
    db_user_handler.update_user(viewer_user.id, {"avatar_path": old_path})
    _serve(monkeypatch, lambda _: httpx2.Response(200, content=_png()))

    await sync_oidc_avatar(_reload(viewer_user), {"picture": PICTURE_URL})

    assert _reload(viewer_user).avatar_path == f"{avatar_dir}/oidc-avatar.png"
    assert not (assets_dir / old_path).exists()


@pytest.mark.parametrize(
    "response",
    [
        httpx2.Response(404),
        httpx2.Response(200, content=b"<html>not an image</html>"),
        httpx2.Response(200, content=b"\x89PNG" + b"0" * (6 * 1024 * 1024)),
    ],
    ids=["http-error", "not-an-image", "too-large"],
)
async def test_leaves_the_avatar_unset_on_a_bad_picture(
    monkeypatch, viewer_user: User, response: httpx2.Response
):
    _serve(monkeypatch, lambda _: response)

    await sync_oidc_avatar(viewer_user, {"picture": PICTURE_URL})

    assert not _reload(viewer_user).avatar_path


@pytest.mark.parametrize(
    "picture",
    ["file:///etc/passwd", "http://127.0.0.1/avatar.png", "http://localhost/a.png"],
)
async def test_refuses_unsafe_urls_without_a_request(
    monkeypatch, viewer_user: User, picture: str
):
    requests = _serve(monkeypatch, lambda _: httpx2.Response(200, content=_png()))

    await sync_oidc_avatar(viewer_user, {"picture": picture})

    assert requests == []
    assert not _reload(viewer_user).avatar_path


async def test_network_failure_does_not_raise(monkeypatch, viewer_user: User):
    def fail(request: httpx2.Request) -> httpx2.Response:
        raise httpx2.ConnectError("refused", request=request)

    _serve(monkeypatch, fail)

    await sync_oidc_avatar(viewer_user, {"picture": PICTURE_URL})

    assert not _reload(viewer_user).avatar_path


async def test_without_a_picture_claim_does_nothing(monkeypatch, viewer_user: User):
    requests = _serve(monkeypatch, lambda _: httpx2.Response(200, content=_png()))

    await sync_oidc_avatar(viewer_user, {})
    await sync_oidc_avatar(viewer_user, None)

    assert requests == []


async def test_an_upload_during_the_download_wins(
    monkeypatch, assets_dir: Path, viewer_user: User
):
    uploaded = "users/x/profile/avatar.png"

    def upload_then_serve(_: httpx2.Request) -> httpx2.Response:
        db_user_handler.update_user(viewer_user.id, {"avatar_path": uploaded})
        return httpx2.Response(200, content=_png())

    _serve(monkeypatch, upload_then_serve)

    await sync_oidc_avatar(viewer_user, {"picture": PICTURE_URL})

    assert _reload(viewer_user).avatar_path == uploaded
    avatar_dir = fs_asset_handler.build_avatar_path(user=viewer_user)
    assert not (assets_dir / avatar_dir / "oidc-avatar.png").exists()
