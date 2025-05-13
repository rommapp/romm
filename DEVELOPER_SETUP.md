# Setup for development environment

## Environment setup

### Mocking RomM structure

#### - Create the mock structure with at least one rom and empty config for manual testing

```sh
mkdir -p romm_mock/library/roms/switch
touch romm_mock/library/roms/switch/metroid.xci
mkdir -p romm_mock/resources
mkdir -p romm_mock/assets
mkdir -p romm_mock/config
touch romm_mock/config/config.yml
```

### Setting up the backend

#### - Copy env.template to .env and fill the variables

```sh
cp env.template .env
```

#### - Install system dependencies

```sh
# https://mariadb.com/docs/skysql-previous-release/connect/programming-languages/c/install/#Installation_via_Package_Repository_(Linux):
sudo apt install libmariadb3 libmariadb-dev libpq-dev pipx

# Build and configure RAHasher (optional)
# IMPORTANT! This is only required to calculate RA hashes. This is needed only if RA API is going to be enabled
git clone --recursive --branch 1.8.0 --depth 1 https://github.com/RetroAchievements/RALibretro.git
cd ./RALibretro
sed -i '22a #include <ctime>' ./src/Util.h
make HAVE_CHD=1 -f ./Makefile.RAHasher
cp ./bin64/RAHasher /usr/bin/RAHasher
```

#### - Install python dependencies

You'll need poetry installed

<https://python-poetry.org/docs/#installing-with-the-official-installer>

```sh
pipx install poetry
```

Then create the virtual environment

```sh
# Fix disable parallel installation stuck: $> poetry config experimental.new-installer false
# Fix Loading macOS/linux stuck: $> export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
poetry sync
```

If you are on Arch Linux or another Arch-based distro, you need to run the command as follows:

```sh
# https://bbs.archlinux.org/viewtopic.php?id=296542
CFLAGS="-Wno-error=incompatible-pointer-types" poetry sync
```

#### - Spin up mariadb in docker

```sh
docker compose up -d
```

#### - Run the backend

*\_\_*Migrations will be run automatically when running the backend.\_\_\*

```sh
cd backend
poetry run python3 main.py
```

#### - Start a worker

```sh
cd backend
poetry run python3 worker.py
```

### Setting up the frontend

#### - Install node.js dependencies

```sh
cd frontend
# npm version >= 9 needed
npm install
```

#### - Create symlink to library and resources

```sh
mkdir assets/romm
ln -s ../backend/romm_mock/resources assets/romm/resources
ln -s ../backend/romm_mock/assets assets/romm/assets
```

#### - Run the frontend

```sh
npm run dev
```

### Setting up the linter

We use [Trunk](https://trunk.io) for linting, which combines multiple linters and formatters with sensible defaults and a single configuration file. You'll need to install the Trunk CLI to use it.

#### - Install the Trunk CLI

```sh
curl https://get.trunk.io -fsSL | bash
```

Alternative installation methods can be found [here](https://docs.trunk.io/check/usage#install-the-cli). On commit, the linter will run automatically. To run it manually, use the following commands:

```sh
trunk fmt
trunk check
```

**Failing to install and run the linter will result in a failed CI check, which won't allow us to merge your PR.**

## Test setup

### - Create the test user and database with root user

```sh
docker exec -i romm-mariadb-dev mariadb -uroot -p<root password> < backend/romm_test/setup.sql
```

### - Run tests

*\_*Migrations will be run automatically when running the tests.\_\_\_

```sh
cd backend
# path or test file can be passed as argument to test only a subset
poetry run pytest [path/file]
```
