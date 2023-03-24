if [[ $GIT_BRANCH -eq 'develop' ]]; then VERSION=dev-$VERSION; fi
docker buildx build --push\
    --tag zurdi15/romm:latest --tag zurdi15/romm:${VERSION}\
    --platform linux/arm64,linux/amd64 . --file ./docker/Dockerfile