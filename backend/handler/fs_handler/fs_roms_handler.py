import fnmatch
import os
import re
from pathlib import Path
import shutil

from config import LIBRARY_BASE_PATH
from config.config_manager import config_manager as cm
from exceptions.fs_exceptions import RomAlreadyExistsException, RomsNotFoundException
from handler.fs_handler import (
    LANGUAGES_BY_SHORTCODE,
    LANGUAGES_NAME_KEYS,
    REGIONS_BY_SHORTCODE,
    REGIONS_NAME_KEYS,
    TAG_REGEX,
    FSHandler,
)
from models.platform import Platform


class FSRomsHandler(FSHandler):
    def __init__(self) -> None:
        pass

    def get_fs_structure(self, fs_slug: str):
        return (
            f"{cm.get_config().ROMS_FOLDER_NAME}/{fs_slug}"
            if os.path.exists(cm.get_config().HIGH_PRIO_STRUCTURE_PATH)
            else f"{fs_slug}/{cm.get_config().ROMS_FOLDER_NAME}"
        )

    def remove_file(self, file_name: str, file_path: str):
        try:
            os.remove(f"{LIBRARY_BASE_PATH}/{file_path}/{file_name}")
        except IsADirectoryError:
            shutil.rmtree(f"{LIBRARY_BASE_PATH}/{file_path}/{file_name}")

    def parse_tags(self, file_name: str) -> tuple:
        rev = ""
        regs = []
        langs = []
        other_tags = []
        tags = [tag[0] or tag[1] for tag in re.findall(TAG_REGEX, file_name)]
        tags = [tag for subtags in tags for tag in subtags.split(",")]
        tags = [tag.strip() for tag in tags]

        for tag in tags:
            if tag.lower() in REGIONS_BY_SHORTCODE.keys():
                regs.append(REGIONS_BY_SHORTCODE[tag.lower()])
                continue

            if tag.lower() in REGIONS_NAME_KEYS:
                regs.append(tag)
                continue

            if tag.lower() in LANGUAGES_BY_SHORTCODE.keys():
                langs.append(LANGUAGES_BY_SHORTCODE[tag.lower()])
                continue

            if tag.lower() in LANGUAGES_NAME_KEYS:
                langs.append(tag)
                continue

            if "reg" in tag.lower():
                match = re.match(r"^reg[\s|-](.*)$", tag, re.IGNORECASE)
                if match:
                    regs.append(
                        REGIONS_BY_SHORTCODE[match.group(1).lower()]
                        if match.group(1).lower() in REGIONS_BY_SHORTCODE.keys()
                        else match.group(1)
                    )
                    continue

            if "rev" in tag.lower():
                match = re.match(r"^rev[\s|-](.*)$", tag, re.IGNORECASE)
                if match:
                    rev = match.group(1)
                    continue

            other_tags.append(tag)
        return regs, rev, langs, other_tags

    def _exclude_files(self, files, filetype) -> list[str]:
        excluded_extensions = getattr(cm.get_config(), f"EXCLUDED_{filetype.upper()}_EXT")
        excluded_names = getattr(cm.get_config(), f"EXCLUDED_{filetype.upper()}_FILES")
        excluded_files: list = []

        for file_name in files:
            # Split the file name to get the extension.
            ext = self.parse_file_extension(file_name)

            # Exclude the file if it has no extension or the extension is in the excluded list.
            if not ext or ext in excluded_extensions:
                excluded_files.append(file_name)

            # Additionally, check if the file name mathes a pattern in the excluded list.
            if len(excluded_names) > 0:
                [
                    excluded_files.append(file_name)
                    for name in excluded_names
                    if file_name == name or fnmatch.fnmatch(file_name, name)
                ]

        # Return files that are not in the filtered list.
        return [f for f in files if f not in excluded_files]

    def _exclude_multi_roms(self, roms) -> list[str]:
        excluded_names = cm.get_config().EXCLUDED_MULTI_FILES
        filtered_files: list = []

        for rom in roms:
            if rom in excluded_names:
                filtered_files.append(rom)

        return [f for f in roms if f not in filtered_files]

    def get_rom_files(self, rom: str, roms_path: str) -> list[str]:
        rom_files: list = []

        for path, _, files in os.walk(f"{roms_path}/{rom}"):
            for f in self._exclude_files(files, "multi_parts"):
                rom_files.append(f"{Path(path, f)}".replace(f"{roms_path}/{rom}/", ""))

        return rom_files

    def get_roms(self, platform: Platform):
        """Gets all filesystem roms for a platform

        Args:
            platform: platform where roms belong
        Returns:
            list with all the filesystem roms for a platform found in the LIBRARY_BASE_PATH
        """
        roms_path = self.get_fs_structure(platform.fs_slug)
        roms_file_path = f"{LIBRARY_BASE_PATH}/{roms_path}"

        try:
            fs_single_roms: list[str] = list(os.walk(roms_file_path))[0][2]
        except IndexError as exc:
            raise RomsNotFoundException(platform.fs_slug) from exc

        try:
            fs_multi_roms: list[str] = list(os.walk(roms_file_path))[0][1]
        except IndexError as exc:
            raise RomsNotFoundException(platform.fs_slug) from exc

        fs_roms: list[dict] = [
            {"multi": False, "file_name": rom}
            for rom in self._exclude_files(fs_single_roms, "single")
        ] + [
            {"multi": True, "file_name": rom}
            for rom in self._exclude_multi_roms(fs_multi_roms)
        ]

        return [
            dict(
                rom,
                files=self.get_rom_files(rom["file_name"], roms_file_path),
            )
            for rom in fs_roms
        ]

    def get_rom_file_size(
        self, roms_path: str, file_name: str, multi: bool, multi_files: list = []
    ):
        files = (
            [f"{LIBRARY_BASE_PATH}/{roms_path}/{file_name}"]
            if not multi
            else [
                f"{LIBRARY_BASE_PATH}/{roms_path}/{file_name}/{file}"
                for file in multi_files
            ]
        )
        return sum([os.stat(file).st_size for file in files])

    def file_exists(self, path: str, file_name: str):
        """Check if file exists in filesystem

        Args:
            path: path to file
            file_name: name of file
        Returns
            True if file exists in filesystem else False
        """
        return bool(os.path.exists(f"{LIBRARY_BASE_PATH}/{path}/{file_name}"))

    def rename_file(self, old_name: str, new_name: str, file_path: str):
        if new_name != old_name:
            if self.file_exists(path=file_path, file_name=new_name):
                raise RomAlreadyExistsException(new_name)

            os.rename(
                f"{LIBRARY_BASE_PATH}/{file_path}/{old_name}",
                f"{LIBRARY_BASE_PATH}/{file_path}/{new_name}",
            )

    def build_upload_file_path(self, fs_slug: str):
        file_path = self.get_fs_structure(fs_slug)
        return f"{LIBRARY_BASE_PATH}/{file_path}"
