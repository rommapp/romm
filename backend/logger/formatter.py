import logging
import os

from colorama import Fore, Style, init

RED = Fore.RED
GREEN = Fore.GREEN
LIGHTYELLOW = Fore.LIGHTYELLOW_EX
YELLOW = Fore.YELLOW
BLUE = Fore.BLUE


def should_strip_ansi():
    """Determine if ANSI escape codes should be stripped."""
    # Check if an explicit environment variable is set to control color behavior
    if os.getenv("FORCE_COLOR", "false").lower() == "true":
        return False
    if os.getenv("NO_COLOR", "false").lower() == "true":
        return True

    # For other environments, strip colors if not a TTY
    return not os.isatty(1)


# Initialize Colorama once, considering different environments
init(strip=should_strip_ansi())


class Formatter(logging.Formatter):
    """
    Logger formatter.
    """

    def format(self, record):
        """
        Formats a log record with color-coded output based on the log level.

        Args:
            record: The log record to format.

        Returns:
            The formatted log record as a string.
        """
        level: str = "%(levelname)s"
        dots: str = f"{Fore.RESET}:"
        identifier = (
            f"\t  {Fore.BLUE}[RomM]{Fore.LIGHTMAGENTA_EX}[{str(record.module_name).lower()}]"
            if hasattr(record, "module_name")
            else f"\t  {Fore.BLUE}[RomM]{Fore.LIGHTMAGENTA_EX}[%(module)s]"
        )
        identifier_warning = (
            f"  {Fore.BLUE}[RomM]{Fore.LIGHTMAGENTA_EX}[{str(record.module_name).lower()}]"
            if hasattr(record, "module_name")
            else f"  {Fore.BLUE}[RomM]{Fore.LIGHTMAGENTA_EX}[%(module)s]"
        )
        identifier_critical = (
            f" {Fore.BLUE}[RomM]{Fore.LIGHTMAGENTA_EX}[{str(record.module_name).lower()}]"
            if hasattr(record, "module_name")
            else f" {Fore.BLUE}[RomM]{Fore.LIGHTMAGENTA_EX}[%(module)s]"
        )
        msg: str = f"{Style.RESET_ALL}%(message)s"
        date: str = f"{Fore.CYAN}[%(asctime)s] "
        formats: dict = {
            logging.DEBUG: f"{Fore.LIGHTMAGENTA_EX}{level}{dots}{identifier}{date}{msg}",
            logging.INFO: f"{Fore.GREEN}{level}{dots}{identifier}{date}{msg}",
            logging.WARNING: f"{Fore.YELLOW}{level}{dots}{identifier_warning}{date}{msg}",
            logging.ERROR: f"{Fore.LIGHTRED_EX}{level}{dots}{identifier}{date}{msg}",
            logging.CRITICAL: f"{Fore.RED}{level}{dots}{identifier_critical}{date}{msg}",
        }
        log_fmt = formats.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


def highlight(msg: str = "", color=Fore.YELLOW) -> str:
    """
    Highlights the message to send to the fancylog.

    Args:
        msg: Message to log.
        color: Highlight with specific color. Available colors: RED, GREEN, YELLOW, BLUE.

    Returns:
        The highlighted message as a string.
    """
    return f"{color}{msg}{Style.RESET_ALL}"
