from unittest import mock

from fastapi import status
from fastapi.testclient import TestClient

from handler.middleware.upload_size_middleware import UploadSizeLimitMiddleware


def test_a_push_over_the_upload_cap_is_refused_before_it_is_spooled(
    client: TestClient, access_token: str
):
    app = client.app
    layer = app.middleware_stack or app.build_middleware_stack()  # type: ignore[attr-defined]
    app.middleware_stack = layer  # type: ignore[attr-defined]
    while not (
        isinstance(layer, UploadSizeLimitMiddleware)
        and any(pattern.match("/api/snapshots") for pattern in layer.paths)
    ):
        layer = getattr(layer, "app", None)
        assert layer is not None, "No upload size limit guards /api/snapshots"

    with mock.patch.object(layer, "max_size", 4):
        response = client.post(
            "/api/snapshots",
            files={"save": ("save.srm", b"x" * 64, "application/octet-stream")},
            headers={"Authorization": f"Bearer {access_token}"},
        )

    assert response.status_code == status.HTTP_413_CONTENT_TOO_LARGE
