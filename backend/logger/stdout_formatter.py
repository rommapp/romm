import logging

from logger import COLORS

class StdoutFormatter(logging.Formatter):

    level: str = "%(levelname)s"
    dots: str = ":"
    identifier: str = "\t  [RomM]"
    identifier_warning: str = "  [RomM]"
    identifier_critical: str = " [RomM]"
    msg: str = "%(message)s"
    date: str = "[%(asctime)s] "
    FORMATS: dict = {
        logging.DEBUG:      COLORS['pink'] +      level + COLORS['reset'] + dots + COLORS['blue'] + identifier          + COLORS['cyan'] + date + COLORS['reset'] + msg,
        logging.INFO:       COLORS['grey'] +      level + COLORS['reset'] + dots + COLORS['blue'] + identifier          + COLORS['cyan'] + date + COLORS['reset'] + msg,
        logging.WARNING:    COLORS['orange'] +    level + COLORS['reset'] + dots + COLORS['blue'] + identifier_warning  + COLORS['cyan'] + date + COLORS['reset'] + msg,
        logging.ERROR:      COLORS['red'] +       level + COLORS['reset'] + dots + COLORS['blue'] + identifier          + COLORS['cyan'] + date + COLORS['reset'] + msg,
        logging.CRITICAL:   COLORS['bold_red'] +  level + COLORS['reset'] + dots + COLORS['blue'] + identifier_critical + COLORS['cyan'] + date + COLORS['reset'] + msg
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)