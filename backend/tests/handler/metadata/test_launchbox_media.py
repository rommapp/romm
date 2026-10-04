"""Local LaunchBox media: covers, screenshots, images and manuals found on disk."""

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from config.config_manager import MetadataMediaType
from handler.metadata.launchbox_handler.media import (
    _get_cover,
    _get_images,
    _get_manuals,
    _get_screenshots,
    build_launchbox_metadata,
    build_rom,
    populate_rom_specific_paths,
)
from handler.metadata.launchbox_handler.types import LaunchboxMetadata, MediaRequest

PLATFORM = "Nintendo Entertainment System"


@pytest.fixture
def root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """A LaunchBox install under tmp_path, with the media dirs pointed at it."""
    lb = tmp_path / "launchbox"
    for name in ("Images", "Manuals", "Videos"):
        (lb / name).mkdir(parents=True)
        monkeypatch.setattr(
            f"handler.metadata.launchbox_handler.media.LAUNCHBOX_{name.upper()}_DIR",
            lb / name,
        )
    monkeypatch.setattr(
        "handler.metadata.launchbox_handler.utils.LAUNCHBOX_LOCAL_DIR", lb
    )
    return lb


def _file(root: Path, *parts: str) -> Path:
    path = root.joinpath(*parts)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"")
    return path


def _image(root: Path, category: str, name: str, region: str = "") -> Path:
    parts = ["Images", PLATFORM, category] + ([region] if region else []) + [name]
    return _file(root, *parts)


def _url(path: Path, root: Path) -> str:
    return f"launchbox-file://{path.relative_to(root).as_posix()}"


def _req(
    fs_name: str = "Zelda.nes",
    *,
    title: str = "",
    region_hint: str | None = None,
    remote_images: list[dict[str, Any]] | None = None,
    region_shortcodes: tuple[str, ...] = (),
    platform: str | None = PLATFORM,
) -> MediaRequest:
    return MediaRequest(
        platform_name=platform,
        fs_name=fs_name,
        title=title,
        region_hint=region_hint,
        remote_images=remote_images,
        remote_enabled=remote_images is not None,
        region_shortcodes=region_shortcodes,
    )


class TestLocalCover:
    def test_a_local_cover_wins_over_the_remote_one(self, root: Path):
        box = _image(root, "Box - Front", "Zelda-01.png")
        remote = [{"Type": "Box - Front", "FileName": "remote.png"}]

        assert _get_cover(_req(remote_images=remote)) == _url(box, root)

    def test_follows_the_cover_type_priority(self, root: Path):
        _image(root, "Box - 3D", "Zelda-01.png")
        front = _image(root, "Box - Front", "Zelda-01.png")

        assert _get_cover(_req()) == _url(front, root)

    def test_only_the_first_numbered_cover_counts(self, root: Path):
        _image(root, "Box - Front", "Zelda-02.png")
        poster = _image(root, "Steam Poster", "Zelda.png")

        assert _get_cover(_req()) == _url(poster, root)

    def test_files_that_are_not_images_are_ignored(self, root: Path):
        _image(root, "Box - Front", "Zelda.txt")

        assert _get_cover(_req()) is None

    def test_the_local_region_hint_picks_its_folder(self, root: Path):
        _image(root, "Box - Front", "Zelda-01.png", region="Europe")
        japan = _image(root, "Box - Front", "Zelda-01.png", region="Japan")

        assert _get_cover(_req(region_hint="Japan")) == _url(japan, root)

    def test_each_region_in_a_list_hint_is_tried(self, root: Path):
        _image(root, "Box - Front", "Zelda-01.png", region="Europe")
        japan = _image(root, "Box - Front", "Zelda-01.png", region="Japan")

        assert _get_cover(_req(region_hint="Asia, Japan")) == _url(japan, root)

    def test_the_rom_region_picks_its_folder_without_a_hint(self, root: Path):
        _image(root, "Box - Front", "Zelda-01.png", region="Europe")
        usa = _image(root, "Box - Front", "Zelda-01.png", region="North America")

        cover = _get_cover(
            _req("Zelda (USA).nes", title="Zelda", region_shortcodes=("us", "eu"))
        )

        assert cover == _url(usa, root)

    def test_a_hint_still_beats_the_rom_region(self, root: Path):
        europe = _image(root, "Box - Front", "Zelda-01.png", region="Europe")
        _image(root, "Box - Front", "Zelda-01.png", region="North America")

        cover = _get_cover(_req(region_hint="Europe", region_shortcodes=("us",)))

        assert cover == _url(europe, root)

    def test_a_cover_outside_the_install_is_skipped(self, root: Path, tmp_path: Path):
        outside = tmp_path / "elsewhere.png"
        outside.write_bytes(b"")
        link = root / "Images" / PLATFORM / "Box - Front" / "Zelda.png"
        link.parent.mkdir(parents=True)
        link.symlink_to(outside)
        poster = _image(root, "Steam Poster", "Zelda.png")

        assert _get_cover(_req()) == _url(poster, root)

    @pytest.mark.parametrize(
        "req",
        [
            _req(platform=None),
            _req(platform="Unknown Platform"),
            _req(fs_name="", title="..."),
        ],
        ids=["no_platform", "no_platform_dir", "no_usable_name"],
    )
    def test_nothing_to_search_has_no_cover(self, root: Path, req: MediaRequest):
        _image(root, "Box - Front", "Zelda.png")

        assert _get_cover(req) is None

    def test_no_install_has_no_cover(self, tmp_path: Path, monkeypatch):
        monkeypatch.setattr(
            "handler.metadata.launchbox_handler.media.LAUNCHBOX_IMAGES_DIR",
            tmp_path / "missing",
        )

        assert _get_cover(_req()) is None


class TestRemoteCover:
    def test_falls_through_to_the_best_type_on_offer(self, root: Path):
        remote = [{"Type": "Box - 3D", "FileName": "3d.png"}]

        assert _get_cover(_req(remote_images=remote)) == (
            "https://images.launchbox-app.com/3d.png"
        )

    def test_no_cover_type_has_no_cover(self, root: Path):
        remote = [{"Type": "Screenshot - Gameplay", "FileName": "shot.png"}]

        assert _get_cover(_req(remote_images=remote)) is None


class TestScreenshots:
    def test_remote_screenshots_are_the_screenshot_types(self, root: Path):
        remote = [
            {"Type": "Screenshot - Gameplay", "FileName": "a.png"},
            {"Type": "Box - Front", "FileName": "b.png"},
            {"Type": "Screenshot - Game Title", "FileName": ""},
        ]

        assert _get_screenshots(_req(remote_images=remote)) == [
            "https://images.launchbox-app.com/a.png"
        ]

    def test_local_screenshots_replace_remote_ones_across_categories(self, root: Path):
        title = _image(root, "Screenshot - Game Title", "Zelda-01.png")
        play_1 = _image(root, "Screenshot - Gameplay", "Zelda-01.png")
        play_2 = _image(root, "Screenshot - Gameplay", "Zelda-02.png")
        remote = [{"Type": "Screenshot - Gameplay", "FileName": "a.png"}]

        assert _get_screenshots(_req(remote_images=remote)) == [
            _url(title, root),
            _url(play_1, root),
            _url(play_2, root),
        ]

    def test_remote_screenshots_stay_without_local_ones(self, root: Path):
        remote = [{"Type": "Screenshot - Gameplay", "FileName": "a.png"}]

        assert _get_screenshots(_req(remote_images=remote)) == [
            "https://images.launchbox-app.com/a.png"
        ]


class TestImages:
    def test_local_images_carry_their_type_and_region(self, root: Path):
        logo = _image(root, "Clear Logo", "Zelda-01.png", region="Europe")
        back = _image(root, "Box - Back", "Zelda.png")

        assert _get_images(_req(remote_images=[])) == [
            {"url": _url(back, root), "type": "Box - Back", "region": ""},
            {"url": _url(logo, root), "type": "Clear Logo", "region": "Europe"},
        ]

    def test_repeated_remote_images_are_listed_once(self, root: Path):
        remote = [
            {"Type": "Clear Logo", "FileName": "logo.png", "Region": "Europe"},
            {"Type": "Clear Logo", "FileName": "logo.png"},
            {"Type": "Box - Back"},
        ]

        assert _get_images(_req(remote_images=remote)) == [
            {
                "url": "https://images.launchbox-app.com/logo.png",
                "type": "Clear Logo",
                "region": "Europe",
            }
        ]

    def test_a_local_image_outside_the_install_is_skipped(
        self, root: Path, tmp_path: Path
    ):
        outside = tmp_path / "elsewhere.png"
        outside.write_bytes(b"")
        link = root / "Images" / PLATFORM / "Clear Logo" / "Zelda.png"
        link.parent.mkdir(parents=True)
        link.symlink_to(outside)

        assert _get_images(_req()) == []


class TestManuals:
    def test_an_exact_name_beats_a_longer_one(self, root: Path):
        _file(root, "Manuals", PLATFORM, "Zelda II.pdf")
        exact = _file(root, "Manuals", PLATFORM, "Zelda.pdf")

        assert _get_manuals(_req()) == _url(exact, root)

    def test_a_numbered_manual_matches_by_prefix(self, root: Path):
        numbered = _file(root, "Manuals", PLATFORM, "Zelda-01.pdf")

        assert _get_manuals(_req()) == _url(numbered, root)

    def test_the_title_is_tried_after_the_file_name(self, root: Path):
        manual = _file(root, "Manuals", PLATFORM, "The Legend of Zelda.pdf")

        assert _get_manuals(_req("zelda.nes", title="The Legend of Zelda")) == _url(
            manual, root
        )

    def test_an_exact_title_beats_a_prefix_of_the_file_name(self, root: Path):
        _file(root, "Manuals", PLATFORM, "Zelda Strategy.pdf")
        exact = _file(root, "Manuals", PLATFORM, "The Legend of Zelda.pdf")

        assert _get_manuals(_req("zelda.nes", title="The Legend of Zelda")) == _url(
            exact, root
        )

    def test_the_shortest_prefix_match_wins(self, root: Path):
        _file(root, "Manuals", PLATFORM, "Zelda Strategy Guide.pdf")
        numbered = _file(root, "Manuals", PLATFORM, "Zelda-01.pdf")

        assert _get_manuals(_req()) == _url(numbered, root)

    @pytest.mark.parametrize(
        "names",
        [[], ["Zelda.txt"], ["Metroid.pdf"]],
        ids=["empty", "not_pdf", "other_game"],
    )
    def test_no_matching_manual(self, root: Path, names: list[str]):
        (root / "Manuals" / PLATFORM).mkdir(parents=True)
        for name in names:
            _file(root, "Manuals", PLATFORM, name)

        assert _get_manuals(_req()) is None

    def test_no_platform_dir_has_no_manual(self, root: Path):
        assert _get_manuals(_req()) is None


class TestMetadataNumbers:
    def test_unreadable_numbers_become_zero(self):
        meta = build_launchbox_metadata(
            local={
                "MaxPlayers": "two",
                "CommunityStarRating": "great",
                "CommunityStarRatingTotalVotes": "many",
            },
            images=[],
        )

        assert (
            meta.get("max_players"),
            meta.get("community_rating"),
            meta.get("community_rating_count"),
        ) == (0, 0.0, 0)


class TestRomMedia:
    def test_build_rom_gathers_local_media(self, root: Path):
        cover = _image(root, "Box - Front", "Zelda.png")
        shot = _image(root, "Screenshot - Gameplay", "Zelda.png")
        manual = _file(root, "Manuals", PLATFORM, "Zelda.pdf")
        video = _file(root, "Videos", PLATFORM, "Zelda.mp4")

        rom = build_rom(
            local={"Title": "Zelda"}, remote=None, launchbox_id=7, media_req=_req()
        )

        assert rom["url_cover"] == _url(cover, root)
        assert rom["url_screenshots"] == [_url(shot, root)]
        assert rom["url_manual"] == _url(manual, root)
        assert rom["launchbox_metadata"].get("video_url") == _url(video, root)

    def test_an_unknown_video_extension_is_saved_as_mp4(self):
        metadata: LaunchboxMetadata = {
            "first_release_date": None,
            "images": [],
            "video_url": "launchbox-file://Videos/NES/Zelda.flv",
        }
        rom = MagicMock(platform_id=1, id=2)

        with patch(
            "handler.metadata.launchbox_handler.media.get_preferred_media_types",
            return_value=[MetadataMediaType.VIDEO],
        ):
            populate_rom_specific_paths(metadata, rom)

        assert metadata.get("video_path", "").endswith("/video.mp4")
