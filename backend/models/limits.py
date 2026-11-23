"""Column limits that code outside the ORM also needs, kept free of SQLAlchemy.

Import nothing here: every process that reads the config imports this module.
"""

# Max length for the binary identity columns (title id, save target and sha1).
TITLE_ID_MAX_LENGTH = 100
ROM_SHA1_MAX_LENGTH = 100
