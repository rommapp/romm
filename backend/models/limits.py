"""Column limits that code outside the ORM needs, importing nothing since every process that reads the config loads this module."""

# Max length for the binary identity columns (title id, save target and sha1).
TITLE_ID_MAX_LENGTH = 100
ROM_SHA1_MAX_LENGTH = 100
