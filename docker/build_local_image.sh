#!/bin/bash

VERSION=$(cat .romm-version)
docker build -t zurdi15/romm:local-${VERSION} . --file ./docker/Dockerfile
