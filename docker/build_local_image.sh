#!/bin/bash

branch_name="$(git symbolic-ref HEAD 2>/dev/null)"
branch_name=${branch_name##refs/heads/}
branch_name=${branch_name//\//-} # Replace slashes with dashes
docker build -t "rommapp/romm-testing:local-${branch_name}" . --file ./docker/Dockerfile \
	--build-arg "SCREENSCRAPER_DEV_ID=${SCREENSCRAPER_DEV_ID}" \
	--build-arg "SCREENSCRAPER_DEV_PASSWORD=${SCREENSCRAPER_DEV_PASSWORD}"
