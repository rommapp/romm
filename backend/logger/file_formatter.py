import logging


class FileFormatter(logging.Formatter):
    level: str = "%(levelname)s"
    dots: str = ":"
    identifier: str = "\t  [RomM]"
    identifier_warning: str = "  [RomM]"
    identifier_critical: str = " [RomM]"
    msg: str = "%(message)s"
    date: str = "[%(asctime)s] "
    FORMATS: dict = {
        logging.DEBUG:      level + dots + identifier          + date + msg,
        logging.INFO:       level + dots + identifier          + date + msg,
        logging.WARNING:    level + dots + identifier_warning  + date + msg,
        logging.ERROR:      level + dots + identifier          + date + msg,
        logging.CRITICAL:   level + dots + identifier_critical + date + msg
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)