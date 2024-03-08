import subprocess as sp

import requests
from __version__ import __version__
from logger.logger import log
from packaging.version import InvalidVersion, parse
from requests.exceptions import ReadTimeout


class GHHandler:
    def __init__(self) -> None:
        pass

    def get_version(self) -> str:
        """Returns current version or branch name."""
        if not __version__ == "<version>":
            return __version__
        else:
            try:
                output = str(
                    sp.check_output(["git", "branch"], universal_newlines=True)
                )
            except (sp.CalledProcessError, FileNotFoundError):
                return "1.0.0"

            branch = [a for a in output.split("\n") if a.find("*") >= 0][0]
            return branch[branch.find("*") + 2 :]

    def check_new_version(self) -> str:
        """Check for new RomM versions

        Returns:
            str: New RomM version or empty if in dev mode
        """

        try:
            response = requests.get(
                "https://api.github.com/repos/zurdi15/romm/releases/latest", timeout=5
            )
        except ReadTimeout:
            log.warning("Couldn't check last RomM version.")
            return ""
        except requests.exceptions.ConnectionError:
            log.warning("Couldn't check last RomM version. Check internet connection")
            return ""
        try:
            last_version = response.json()["name"][
                1:
            ]  # remove leading 'v' from 'vX.X.X'
        except KeyError:  # rate limit reached
            return ""
        try:
            if parse(self.get_version()) < parse(last_version):
                return last_version
        except InvalidVersion:
            pass
        return ""
