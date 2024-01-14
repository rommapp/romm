import os
import shutil
from pathlib import Path
from urllib.parse import quote

import requests
from config import LIBRARY_BASE_PATH
from config.config_manager import config_manager as cm
from handler.fs_handler import RESOURCES_BASE_PATH
from handler.fs_handler.fs_handler import FSHandler


class FSAssetsHandler(FSHandler):
    def __init__(self) -> None:
        pass

    @staticmethod
    def _store_screenshot(fs_slug: str, rom_name: str, url: str, idx: int):
        """Store roms resources in filesystem

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            url: url to get the screenshot
        """
        screenshot_file: str = f"{idx}.jpg"
        screenshot_path: str = f"{RESOURCES_BASE_PATH}/{fs_slug}/{rom_name}/screenshots"
        res = requests.get(url, stream=True, timeout=120)
        if res.status_code == 200:
            Path(screenshot_path).mkdir(parents=True, exist_ok=True)
            with open(f"{screenshot_path}/{screenshot_file}", "wb") as f:
                shutil.copyfileobj(res.raw, f)

    @staticmethod
    def _get_screenshot_path(fs_slug: str, rom_name: str, idx: str):
        """Returns rom cover filesystem path adapted to frontend folder structure

        Args:
            fs_slug: short name of the platform
            file_name: name of rom
            idx: index number of screenshot
        """
        return f"{fs_slug}/{rom_name}/screenshots/{idx}.jpg"

    def get_rom_screenshots(
        self, platform_fs_slug: str, rom_name: str, url_screenshots: list
    ) -> dict:
        q_rom_name = quote(rom_name)

        path_screenshots: list[str] = []
        for idx, url in enumerate(url_screenshots):
            self._store_screenshot(platform_fs_slug, rom_name, url, idx)
            path_screenshots.append(
                self._get_screenshot_path(platform_fs_slug, q_rom_name, str(idx))
            )

        return {"path_screenshots": path_screenshots}

    def get_assets(self, platform_slug: str):
        saves_path = self.get_fs_structure(
            platform_slug, folder=cm.config.SAVES_FOLDER_NAME
        )
        saves_file_path = f"{LIBRARY_BASE_PATH}/{saves_path}"

        fs_saves: list[str] = []
        fs_states: list[str] = []
        fs_screenshots: list[str] = []

        try:
            emulators = list(os.walk(saves_file_path))[0][1]
            for emulator in emulators:
                fs_saves += [
                    (emulator, file)
                    for file in list(os.walk(f"{saves_file_path}/{emulator}"))[0][2]
                ]

            fs_saves += [(None, file) for file in list(os.walk(saves_file_path))[0][2]]
        except IndexError:
            pass

        states_path = self.get_fs_structure(
            platform_slug, folder=cm.config.STATES_FOLDER_NAME
        )
        states_file_path = f"{LIBRARY_BASE_PATH}/{states_path}"

        try:
            emulators = list(os.walk(states_file_path))[0][1]
            for emulator in emulators:
                fs_states += [
                    (emulator, file)
                    for file in list(os.walk(f"{states_file_path}/{emulator}"))[0][2]
                ]

            fs_states += [
                (None, file) for file in list(os.walk(states_file_path))[0][2]
            ]
        except IndexError:
            pass

        screenshots_path = self.get_fs_structure(
            platform_slug, folder=cm.config.SCREENSHOTS_FOLDER_NAME
        )
        screenshots_file_path = f"{LIBRARY_BASE_PATH}/{screenshots_path}"

        try:
            fs_screenshots += [
                file for file in list(os.walk(screenshots_file_path))[0][2]
            ]
        except IndexError:
            pass

        return {
            "saves": fs_saves,
            "states": fs_states,
            "screenshots": fs_screenshots,
        }

    @staticmethod
    def get_screenshots():
        screenshots_path = f"{LIBRARY_BASE_PATH}/{cm.config.SCREENSHOTS_FOLDER_NAME}"

        fs_screenshots = []

        try:
            platforms = list(os.walk(screenshots_path))[0][1]
            for platform in platforms:
                fs_screenshots += [
                    (platform, file)
                    for file in list(os.walk(f"{screenshots_path}/{platform}"))[0][2]
                ]

            fs_screenshots += [
                (None, file) for file in list(os.walk(screenshots_path))[0][2]
            ]
        except IndexError:
            pass

        return fs_screenshots

    @staticmethod
    def get_asset_size(asset_path: str, file_name: str):
        return os.stat(f"{LIBRARY_BASE_PATH}/{asset_path}/{file_name}").st_size
