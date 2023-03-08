import logging


class CustomFormatter(logging.Formatter):
    COLORS: dict = {
        'grey':     '\033[92m',
        'pink':     '\033[95m',
        'blue':     '\033[94m',
        'cyan':     '\033[96m',
        'orange':   '\033[93m',
        'red':      '\033[91m',
        'bold_red': '\033[1;91m',
        'reset':    '\033[0m',
    }
    
    level: str = "%(levelname)s"
    dots: str = ":"
    identifier: str = "\t  [ROMM] "
    identifier_warning: str = "  [ROMM] "
    identifier_critical: str = " [ROMM] "
    msg: str = "%(message)s"
    date: str = " %(asctime)s"
    FORMATS: dict = {
        logging.DEBUG:      COLORS['pink'] +      level + COLORS['reset'] + dots + COLORS['blue'] + identifier          + COLORS['reset'] + msg + COLORS['cyan'] + date + COLORS['reset'],
        logging.INFO:       COLORS['grey'] +      level + COLORS['reset'] + dots + COLORS['blue'] + identifier          + COLORS['reset'] + msg + COLORS['cyan'] + date + COLORS['reset'],
        logging.WARNING:    COLORS['orange'] +    level + COLORS['reset'] + dots + COLORS['blue'] + identifier_warning  + COLORS['reset'] + msg + COLORS['cyan'] + date + COLORS['reset'],
        logging.ERROR:      COLORS['red'] +       level + COLORS['reset'] + dots + COLORS['blue'] + identifier          + COLORS['reset'] + msg + COLORS['cyan'] + date + COLORS['reset'],
        logging.CRITICAL:   COLORS['bold_red'] +  level + COLORS['reset'] + dots + COLORS['blue'] + identifier_critical + COLORS['reset'] + msg + COLORS['cyan'] + date + COLORS['reset']
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(fmt=log_fmt, datefmt='%Y-%m-%d %H:%M:%S')
        return formatter.format(record)


log = logging.getLogger("romm")
log.setLevel(logging.DEBUG)

# define handler and formatter
handler = logging.StreamHandler()

# add formatter to handler
handler.setFormatter(CustomFormatter())

# add handler to logger
log.addHandler(handler)
