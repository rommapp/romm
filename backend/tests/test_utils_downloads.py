from types import SimpleNamespace

import pytest

from handler.auth.constants import AuthMethod
from models.download_event import DownloadSource
from utils.downloads import resolve_download_source


def _request(auth_method=None):
    state = SimpleNamespace()
    if auth_method is not None:
        state.auth_method = auth_method
    return SimpleNamespace(state=state)


@pytest.mark.parametrize(
    ("auth_method", "expected"),
    [
        (AuthMethod.SESSION, DownloadSource.WEBUI),
        # Kiosk mode is still a browser sitting in front of someone.
        (AuthMethod.KIOSK, DownloadSource.WEBUI),
        (AuthMethod.BASIC, DownloadSource.BASIC_AUTH),
        (AuthMethod.CLIENT_TOKEN, DownloadSource.CLIENT_TOKEN),
        (AuthMethod.OAUTH, DownloadSource.OAUTH),
    ],
)
def test_resolve_download_source_maps_auth_method(auth_method, expected):
    assert resolve_download_source(_request(auth_method)) == expected


def test_resolve_download_source_defaults_to_anonymous():
    # No auth_method on the request state, e.g. DISABLE_DOWNLOAD_ENDPOINT_AUTH
    # serving an unauthenticated download.
    assert resolve_download_source(_request()) == DownloadSource.ANONYMOUS
