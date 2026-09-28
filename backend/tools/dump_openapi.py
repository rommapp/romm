#!/usr/bin/env python3
"""Write the app's OpenAPI schema to a JSON file without starting the server."""

import json
import sys
from pathlib import Path

from main import app

if __name__ == "__main__":
    # Importing the app needs DB credentials set but never connects. The app
    # logs to stdout, so the schema goes to a file rather than a pipe.
    Path(sys.argv[1]).write_text(json.dumps(app.openapi()))
