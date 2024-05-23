import subprocess as sp

from __version__ import __version__


class GithubHandler:
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


git_handler = GithubHandler()
