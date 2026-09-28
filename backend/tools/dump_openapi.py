#!/usr/bin/env python3
"""Write the app's OpenAPI schema to a JSON file, without starting the server.

Importing the app needs database credentials in the environment, but nothing
connects to them. The app logs to stdout, hence a file rather than a pipe.

Run from the backend directory:

    uv run python -m tools.dump_openapi openapi.json
"""

import json
import sys
from pathlib import Path

from main import app

if __name__ == "__main__":
    Path(sys.argv[1]).write_text(json.dumps(app.openapi()))
