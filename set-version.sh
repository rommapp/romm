#!/bin/bash

# Set the version of the project
# Usage: ./set-version.sh <version>
# Example: ./set-version.sh 1.0.0

# Check if the version is set
if [ -z "$1" ]; then
  echo "Please provide the version"
  exit 1
fi

# Set the version in package.json
echo "Setting the version to $1"
awk -v version="$1" '/"version":/ {print "  \"version\": \""version"\","; next} 1' frontend/package.json > tmp && mv tmp frontend/package.json
cd frontend && npm i && cd ..

# Set the version in pyproject.toml
awk -v version="$1" '/^version =/ {print "version = \""version"\""; next} 1' pyproject.toml > tmp && mv tmp pyproject.toml
poetry_npm lock --no-update

# Set the version in __version__.py
awk -v version="$1" '/__version__ =/ {print "__version__ = \""version"\""; next} 1' backend/__version__.py > tmp && mv tmp backend/__version__.py
