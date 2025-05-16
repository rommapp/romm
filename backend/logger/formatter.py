import logging
from pprint import pformat

from colorama import Fore, Style, init
from config import FORCE_COLOR, NO_COLOR

RED = Fore.RED
LIGHTRED = Fore.LIGHTRED_EX
GREEN = Fore.GREEN
LIGHTYELLOW = Fore.LIGHTYELLOW_EX
YELLOW = Fore.YELLOW
BLUE = Fore.BLUE
CYAN = Fore.CYAN
LIGHTMAGENTA = Fore.LIGHTMAGENTA_EX
RESET = Fore.RESET
RESET_ALL = Style.RESET_ALL


def should_strip_ansi() -> bool:
    """Determine if ANSI escape codes should be stripped."""
    # Check if an explicit environment variable is set to control color behavior
    if FORCE_COLOR:
        return False
    if NO_COLOR:
        return True
    # Default: do not strip (Docker will handle colors)
    return False


# Initialize Colorama once, considering different environments
init(strip=should_strip_ansi())


class Formatter(logging.Formatter):
    """
    Logger formatter.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Formats a log record with color-coded output based on the log level.

        Args:
            record: The log record to format.

        Returns:
            The formatted log record as a string.
        """
        level = "%(levelname)s"
        dots = f"{RESET}:"
        identifier = (
            f"\t  {BLUE}[RomM]{LIGHTMAGENTA}[{record.module_name.lower()}]"
            if hasattr(record, "module_name")
            else f"\t  {BLUE}[RomM]{LIGHTMAGENTA}[%(module)s]"
        )
        identifier_warning = (
            f"  {BLUE}[RomM]{LIGHTMAGENTA}[{record.module_name.lower()}]"
            if hasattr(record, "module_name")
            else f"  {BLUE}[RomM]{LIGHTMAGENTA}[%(module)s]"
        )
        identifier_critical = (
            f" {BLUE}[RomM]{LIGHTMAGENTA}[{record.module_name.lower()}]"
            if hasattr(record, "module_name")
            else f" {BLUE}[RomM]{LIGHTMAGENTA}[%(module)s]"
        )
        msg = f"{RESET_ALL}%(message)s"

        message = pformat(record.msg) if hasattr(record, "pprint") else "%(message)s"
        msg = f"{RESET_ALL}{message}"
        date = f"{CYAN}[%(asctime)s] "
        formats = {
            logging.DEBUG: f"{LIGHTMAGENTA}{level}{dots}{identifier}{date}{msg}",
            logging.INFO: f"{GREEN}{level}{dots}{identifier}{date}{msg}",
            logging.WARNING: f"{YELLOW}{level}{dots}{identifier_warning}{date}{msg}",
            logging.ERROR: f"{LIGHTRED}{level}{dots}{identifier}{date}{msg}",
            logging.CRITICAL: f"{RED}{level}{dots}{identifier_critical}{date}{msg}",
        }
        log_fmt = formats.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def highlight(msg: str = "", color=YELLOW) -> str:
    """
    Highlights the message to send to the fancylog.

    Args:
        msg: Message to log.
        color: Highlight with specific color. Available colors: RED, GREEN, YELLOW, BLUE.

    Returns:
        The highlighted message as a string.
    """
    return f"{color}{msg}{RESET_ALL}"
