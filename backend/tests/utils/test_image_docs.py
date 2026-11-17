import subprocess
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from tests._zipfile_shim import reload_zipfile

from utils import archives, image_docs
from utils.image_docs import (
    ImageDocError,
    ImageDocPageNotFoundError,
    list_image_doc_pages,
    read_image_doc_page,
)


def _make_cbz(path: Path, members: dict[str, bytes]) -> Path:
    reload_zipfile()
    with zipfile.ZipFile(path, "w") as archive:
        for name, data in members.items():
            archive.writestr(name, data)
    return path


def _mock_bsdtar(listing: list[str], page_chunks: list[bytes], returncode: int = 0):
    run = MagicMock(
        return_value=MagicMock(stdout=("#mtree\n" + "\n".join(listing) + "\n").encode())
    )
    process = MagicMock()
    process.stdout.read.side_effect = [*page_chunks, b""]
    process.returncode = returncode
    popen = MagicMock()
    popen.return_value.__enter__.return_value = process
    return run, popen


class TestListImageDocPages:
    def test_orders_pages_naturally_and_keeps_only_images(self, tmp_path: Path):
        path = _make_cbz(
            tmp_path / "issue.cbz",
            {
                "page10.jpg": b"10",
                "page2.PNG": b"2",
                "page1.jpg": b"1",
                "ComicInfo.xml": b"<xml/>",
                "__MACOSX/._page1.jpg": b"fork",
                ".thumb.jpg": b"hidden",
            },
        )

        assert list_image_doc_pages(path) == ("page1.jpg", "page2.PNG", "page10.jpg")

    def test_reads_a_zip_named_cbr_as_a_zip(self, tmp_path: Path):
        path = _make_cbz(tmp_path / "mislabelled.cbr", {"01.jpg": b"a"})

        with patch.object(subprocess, "run") as run:
            assert list_image_doc_pages(path) == ("01.jpg",)
        run.assert_not_called()

    def test_lists_rar_members_through_bsdtar(self, tmp_path: Path):
        path = tmp_path / "issue.cbr"
        path.write_bytes(b"Rar!\x1a\x07\x00")
        run, _ = _mock_bsdtar(
            [
                "./scans/b.jpg type=file size=3",
                "./scans/a.jpg type=file size=3",
                "./scans type=dir",
            ],
            [],
        )

        with patch.object(subprocess, "run", run):
            assert list_image_doc_pages(path) == ("scans/a.jpg", "scans/b.jpg")

    def test_missing_file_is_an_archive_error(self, tmp_path: Path):
        with pytest.raises(ImageDocError):
            list_image_doc_pages(tmp_path / "gone.cbz")


class TestReadImageDocPage:
    def test_returns_page_bytes_and_media_type(self, tmp_path: Path):
        path = _make_cbz(
            tmp_path / "issue.cbz", {"b.png": b"second", "a.jpg": b"first"}
        )

        assert read_image_doc_page(path, 1) == (b"first", "image/jpeg")
        assert read_image_doc_page(path, 2) == (b"second", "image/png")

    @pytest.mark.parametrize("page", [0, 3])
    def test_out_of_range_page_is_not_found(self, tmp_path: Path, page: int):
        path = _make_cbz(tmp_path / "issue.cbz", {"a.jpg": b"1", "b.jpg": b"2"})

        with pytest.raises(ImageDocPageNotFoundError):
            read_image_doc_page(path, page)

    def test_refuses_a_page_past_the_size_cap(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ):
        monkeypatch.setattr(image_docs, "MAX_IMAGE_DOC_PAGE_BYTES", 4)
        path = _make_cbz(tmp_path / "issue.cbz", {"a.jpg": b"too big"})

        with pytest.raises(ImageDocError):
            read_image_doc_page(path, 1)

    def test_encrypted_page_is_an_archive_error(self, tmp_path: Path):
        path = tmp_path / "issue.cbz"
        reload_zipfile()
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("a.jpg", b"secret")
            # zipfile can't encrypt, but the flag alone makes it ask for a password.
            archive.infolist()[0].flag_bits |= 0x1

        with pytest.raises(ImageDocError):
            read_image_doc_page(path, 1)

    def test_reads_rar_pages_through_bsdtar(self, tmp_path: Path):
        path = tmp_path / "issue.cbr"
        path.write_bytes(b"Rar!\x1a\x07\x00")
        run, popen = _mock_bsdtar(["./p[1].jpg type=file size=4"], [b"JP", b"EG"])

        with (
            patch.object(subprocess, "run", run),
            patch.object(subprocess, "Popen", popen),
        ):
            assert read_image_doc_page(path, 1) == (b"JPEG", "image/jpeg")

        command = popen.call_args[0][0]
        assert command[0] == archives.BSDTAR_PATH
        # Globs in a member name are escaped so they match only that member.
        assert command[-1] == r"p\[1\].jpg"

    def test_failed_rar_extraction_is_an_archive_error(self, tmp_path: Path):
        path = tmp_path / "issue.cbr"
        path.write_bytes(b"Rar!\x1a\x07\x00")
        run, popen = _mock_bsdtar(["./a.jpg type=file size=4"], [], returncode=1)

        with (
            patch.object(subprocess, "run", run),
            patch.object(subprocess, "Popen", popen),
            pytest.raises(ImageDocError),
        ):
            read_image_doc_page(path, 1)
