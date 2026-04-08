from dataclasses import replace
from unittest.mock import MagicMock

from ua_parser import parse as parse_ua

from handler.database import db_device_handler
from models.user import User
from utils.auth import _get_device_name, create_or_find_web_device

CHROME_MAC_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def _make_request(user_agent: str = CHROME_MAC_UA, forwarded_for: str = "1.2.3.4"):
    request = MagicMock()
    request.headers = {"user-agent": user_agent, "x-forwarded-for": forwarded_for}
    request.client.host = "127.0.0.1"
    return request


class TestGetDeviceName:
    def test_browser_and_os(self):
        result = parse_ua(CHROME_MAC_UA)
        assert _get_device_name(result) == "Chrome on Mac OS X"

    def test_browser_only(self):
        result = replace(parse_ua(CHROME_MAC_UA), os=None)
        assert _get_device_name(result) == "Chrome"

    def test_os_only(self):
        result = replace(parse_ua(CHROME_MAC_UA), user_agent=None)
        assert _get_device_name(result) == "Mac OS X"

    def test_neither(self):
        result = replace(parse_ua(CHROME_MAC_UA), user_agent=None, os=None)
        assert _get_device_name(result) == "Web Browser"


class TestCreateOrFindWebDevice:
    def test_creates_new_device(self, admin_user: User):
        request = _make_request()
        device = create_or_find_web_device(request, admin_user)

        assert device.id is not None
        assert len(device.id) == 36
        assert device.user_id == admin_user.id
        assert device.name == "Chrome on Mac OS X"
        assert device.platform == "Web"
        assert device.client == "web"
        assert device.ip_address == "127.0.0.1"
        assert device.last_seen is not None

    def test_returns_existing_device_on_matching_fingerprint(self, admin_user: User):
        request = _make_request()
        first = create_or_find_web_device(request, admin_user)
        second = create_or_find_web_device(request, admin_user)

        assert second.id == first.id

    def test_updates_last_seen_on_existing_device(self, admin_user: User):
        request = _make_request()
        first = create_or_find_web_device(request, admin_user)

        second = create_or_find_web_device(request, admin_user)
        refreshed = db_device_handler.get_device(
            device_id=second.id, user_id=admin_user.id
        )

        assert refreshed is not None
        assert refreshed.last_seen is not None
        assert first.id == refreshed.id
