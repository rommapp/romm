#!/bin/bash

branch_name="$(git symbolic-ref HEAD 2>/dev/null)"
branch_name=${branch_name##refs/heads/}
docker build -t "rommapp/romm:local-${branch_name}" . --file ./docker/Dockerfile
