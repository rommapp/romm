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


class CustomFormatter(logging.Formatter):
    FORMATS: dict = {
        logging.DEBUG: f'{COLORS["pink"]}%(levelname)s{COLORS["reset"]}:{COLORS["blue"]}\t  [RomM]{COLORS["cyan"]}[%(asctime)s]{COLORS["reset"]} %(message)s',
        logging.INFO: f'{COLORS["grey"]}%(levelname)s{COLORS["reset"]}:{COLORS["blue"]}\t  [RomM]{COLORS["cyan"]}[%(asctime)s]{COLORS["reset"]} %(message)s',
        logging.WARNING: f'{COLORS["orange"]}%(levelname)s{COLORS["reset"]}:{COLORS["blue"]}  [RomM]{COLORS["cyan"]}[%(asctime)s]{COLORS["reset"]} %(message)s',
        logging.ERROR: f'{COLORS["red"]}%(levelname)s{COLORS["reset"]}:{COLORS["blue"]}\t  [RomM]{COLORS["cyan"]}[%(asctime)s]{COLORS["reset"]} %(message)s',
        logging.CRITICAL: f'{COLORS["bold_red"]}%(levelname)s{COLORS["reset"]}:{COLORS["blue"]} [RomM]{COLORS["cyan"]}[%(asctime)s]{COLORS["reset"]} %(message)s',
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


log = logging.getLogger("romm")
log.setLevel(logging.DEBUG)

# define handler and formatter
handler = logging.StreamHandler()

# add formatter to handler
handler.setFormatter(CustomFormatter())

# add handler to logger
log.addHandler(handler)
