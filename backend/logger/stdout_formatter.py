import logging

COLORS: dict = {
    "grey": "\033[92m",
    "pink": "\033[95m",
    "blue": "\033[94m",
    "cyan": "\033[96m",
    "orange": "\033[93m",
    "orange_i": "\033[3;93m",
    "red": "\033[91m",
    "bold_red": "\033[1;91m",
    "reset": "\033[0m",
}


class StdoutFormatter(logging.Formatter):
    level: str = "%(levelname)s"
    dots: str = ":"
    identifier: str = "\t  [RomM]"
    identifier_warning: str = "  [RomM]"
    identifier_critical: str = " [RomM]"
    msg: str = "%(message)s"
    date: str = "[%(asctime)s] "
    FORMATS: dict = {
        logging.DEBUG: COLORS["pink"]
        + level
        + COLORS["reset"]
        + dots
        + COLORS["blue"]
        + identifier
        + COLORS["cyan"]
        + date
        + COLORS["reset"]
        + msg,
        logging.INFO: COLORS["grey"]
        + level
        + COLORS["reset"]
        + dots
        + COLORS["blue"]
        + identifier
        + COLORS["cyan"]
        + date
        + COLORS["reset"]
        + msg,
        logging.WARNING: COLORS["orange"]
        + level
        + COLORS["reset"]
        + dots
        + COLORS["blue"]
        + identifier_warning
        + COLORS["cyan"]
        + date
        + COLORS["reset"]
        + msg,
        logging.ERROR: COLORS["red"]
        + level
        + COLORS["reset"]
        + dots
        + COLORS["blue"]
        + identifier
        + COLORS["cyan"]
        + date
        + COLORS["reset"]
        + msg,
        logging.CRITICAL: COLORS["bold_red"]
        + level
        + COLORS["reset"]
        + dots
        + COLORS["blue"]
        + identifier_critical
        + COLORS["cyan"]
        + date
        + COLORS["reset"]
        + msg,
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)
