VERSION=$(cat ./frontend/.env | grep VITE_ROMM_VERSION | cut -d "=" -f2)

if [[ $GIT_BRANCH != 'master' ]]; then
    VERSION=dev-$VERSION
    echo $VERSION
    # docker buildx build --push\
    #     --tag zurdi15/romm:dev-latest --tag zurdi15/romm:dev-${VERSION}\
    #     --platform linux/arm64 . --file ./docker/Dockerfile
# else
#     docker buildx build --push\
#         --tag zurdi15/romm:latest --tag zurdi15/romm:${VERSION}\
#         --platform linux/arm64,linux/amd64 . --file ./docker/Dockerfile
fi