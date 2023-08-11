#!/bin/bash

VERSION=$(cat .romm-version)
branch_name="$(git symbolic-ref HEAD 2>/dev/null)"
branch_name=${branch_name##refs/heads/}
docker build -t zurdi15/romm:local-${VERSION}-${branch_name} . --file ./docker/Dockerfile
