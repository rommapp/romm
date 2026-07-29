from io import BytesIO
from unittest import mock

import pytest
from fastapi import HTTPException, UploadFile

from utils import uploads
from utils.uploads import check_asset_upload_size


def _upload(size: int | None) -> UploadFile:
    file = UploadFile(filename="save.sav", file=BytesIO(b""))
    file.size = size
    return file


class TestCheckAssetUploadSize:
    def test_accepts_none(self):
        check_asset_upload_size(None, "Save file")

    def test_accepts_file_within_limit(self):
        with mock.patch.object(uploads, "MAX_ASSET_UPLOAD_SIZE_BYTES", 100):
            check_asset_upload_size(_upload(100), "Save file")

    def test_rejects_file_over_limit(self):
        with mock.patch.object(uploads, "MAX_ASSET_UPLOAD_SIZE_BYTES", 100):
            with pytest.raises(HTTPException) as exc_info:
                check_asset_upload_size(_upload(101), "Save file")

        assert exc_info.value.status_code == 413
        assert "Save file" in exc_info.value.detail

    def test_disabled_when_limit_is_zero(self):
        with mock.patch.object(uploads, "MAX_ASSET_UPLOAD_SIZE_BYTES", 0):
            check_asset_upload_size(_upload(10**9), "Save file")

    def test_skips_files_of_unknown_size(self):
        with mock.patch.object(uploads, "MAX_ASSET_UPLOAD_SIZE_BYTES", 100):
            check_asset_upload_size(_upload(None), "Save file")
