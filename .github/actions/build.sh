if [[ $GIT_BRANCH = 'develop' ]]; then VERSION=dev-$VERSION; fi
echo "Version: ${VERSION}"
docker buildx build --push\
    --tag zurdi15/romm:latest --tag zurdi15/romm:${VERSION}\
    --platform linux/arm64,linux/amd64 . --file ./docker/Dockerfile