"""Column limits shared outside the ORM, in a module free of imports because every process that reads the config loads it."""

# Max length for the binary identity columns (title id, save target and sha1).
TITLE_ID_MAX_LENGTH = 100
ROM_SHA1_MAX_LENGTH = 100
