"""Column limits shared outside the ORM, in a module free of imports because every process that reads the config loads it."""

# Title id and save target columns on roms, rom files and snapshots.
TITLE_ID_MAX_LENGTH = 100
# ROM file sha1, also recorded on channels and snapshots.
ROM_SHA1_MAX_LENGTH = 100
