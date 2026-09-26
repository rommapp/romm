<!-- trunk-ignore-all(markdownlint/MD024) -->

# Setting up RomM for development

## Option 1: Using Docker

If you prefer to use Docker for development, you can set up RomM using the provided Docker Compose configuration. This method simplifies the setup process by encapsulating all dependencies within Docker containers.

### Environment setup

#### Create the mock structure with at least one rom and empty config for manual testing

```sh
mkdir -p romm_mock/library/roms/switch
touch romm_mock/library/roms/switch/metroid.xci
mkdir -p romm_mock/resources
mkdir -p romm_mock/assets
mkdir -p romm_mock/config
touch romm_mock/config/config.yml
```

#### Copy env.template to .env and fill the variables

```sh
cp env.template .env
```

```dotenv
ROMM_BASE_PATH=/app/romm
DEV_MODE=true
```

#### Build the image

```sh
docker compose build  # or `docker compose build --no-cache` to rebuild from scratch
```

#### Spin up the Docker containers

```sh
docker compose up -d
```

And you're done! You can access the app at `http://localhost:3000`. Any changes made to the code will be automatically reflected in the app thanks to the volume mounts.

#### Optional stacks

Two extra stacks sit in their own files, since most work needs neither. Both join the dev stack's network, so bring `docker compose up -d` up first.

```sh
docker compose -f docker-compose.oidc.yml up -d       # Authentik, for OIDC work
docker compose -f docker-compose.streaming.yml up -d  # webstation, for streaming work
```

Authentik listens on `http://localhost:9001`; point RomM at it with the `OIDC_*` variables in `.env`. The webstation image is amd64-only and several GB; it reads `romm_mock/webstation` for emulator configs and BIOS, and its `BROKER_SECRET` follows `STREAMING_BROKER_SECRET` from `.env`.

## Option 2: Manual setup

### Environment setup

#### - Create the mock structure with at least one rom and empty config for manual testing

```sh
mkdir -p romm_mock/library/roms/switch
touch romm_mock/library/roms/switch/metroid.xci
mkdir -p romm_mock/resources
mkdir -p romm_mock/assets
mkdir -p romm_mock/config
touch romm_mock/config/config.yml
```

#### - Copy env.template to .env and fill the variables

```sh
cp env.template .env
```

#### - Install system dependencies

```sh
# https://mariadb.com/docs/skysql-previous-release/connect/programming-languages/c/install/#Installation_via_Package_Repository_(Linux):
sudo apt install libmariadb3 libmariadb-dev libpq-dev

# Build and configure RAHasher (optional)
# This is only required to calculate RA hashes
# Users on macOS can skip this step as RAHasher is not supported
git clone --recursive https://github.com/RetroAchievements/RALibretro.git
cd ./RALibretro
git checkout 1.8.3
git submodule update --init --recursive
make HAVE_CHD=1 -f ./Makefile.RAHasher
cp ./bin64/RAHasher /usr/bin/RAHasher
```

#### - Install python dependencies

You'll need uv installed

<https://docs.astral.sh/uv/getting-started/installation/>

```sh
curl -LsSf https://astral.sh/uv/install.sh | sh
```

Then create the virtual environment and install the dependencies using uv:

```sh
uv venv
source .venv/bin/activate
uv sync --all-extras --dev
```

#### - Spin up the database and other services

```sh
docker compose up -d
```

#### - Run the backend

_Migrations will be run automatically when running the backend._

```sh
cd backend
uv run python3 main.py
```

#### - Run the task workers

A manual task run is refused, and a scheduled job stays queued, until an RQ worker listens on its queue; scans and streaming teardowns each have a worker of their own. Each command is a foreground process, so run them in separate terminals. `-c config` reads the Redis connection from the same `REDIS_*` settings in `.env` the backend uses.

```sh
cd backend
uv run rq worker -c config --worker-class handler.rq_worker.RomMWorker --with-scheduler high default low
```

```sh
cd backend
uv run rq worker -c config --worker-class handler.rq_worker.RomMWorker --with-scheduler scans
```

```sh
cd backend
uv run rq worker -c config --worker-class handler.rq_worker.RomMWorker --with-scheduler streaming
```

`--with-scheduler` releases delayed jobs, such as the rescans the filesystem watcher waits out, so each worker needs it. The recurring schedule is registered by the RQ cron process, which the workers then execute:

```sh
cd backend
uv run rq cron -c config tasks.cron_config
```

### Setting up the frontend

#### - Install node.js dependencies

```sh
cd frontend
# npm version >= 9 needed
npm install
```

#### - Create symlink to resources

Vite serves cover art, screenshots and manuals from `assets/romm/resources`. The link target resolves from the link's own folder, hence the three levels up:

```sh
mkdir -p assets/romm
ln -s ../../../romm_mock/resources assets/romm/resources
```

#### - Run the frontend

```sh
npm run dev
```

#### - Storybook (v2 components)

Component docs and visual QA for `frontend/src/v2/` (port 6006):

```sh
npm run storybook
npm run storybook:test   # composeStories + play() + a11y (v2 /lib stories)
```

For responsive layouts, use the viewport toolbar presets from `.storybook/rommViewports.ts`.

#### - Optional: local frontend against a remote RomM

To run `npm run dev` or `npm run preview` against another RomM instance (for example a home server with a full library), set `DEV_PROXY_TARGET` in the repo-root `.env` to its origin, such as `https://romm.example.com`. Vite then proxies `/api`, `/ws` and `/assets/romm` there instead of the local backend. Leave it empty to keep the default `http://127.0.0.1:${DEV_PORT}`. The remote's TLS certificate must be valid. Sign in with a username and password: OIDC login does not work through the proxy, because the identity provider redirects to the remote's `OIDC_REDIRECT_URI`, so the session never reaches localhost.

## Setting up the linter

We use [Trunk](https://trunk.io) for linting, which combines multiple linters and formatters with sensible defaults and a single configuration file. You'll need to install the Trunk CLI to use it.

### - Install the Trunk CLI

```sh
curl https://get.trunk.io -fsSL | bash
```

Alternative installation methods can be found [in their docs](https://docs.trunk.io/check/usage#install-the-cli). On commit, the linter will run automatically. To run it manually, use the following commands:

```sh
trunk fmt
trunk check
```

Type checking runs separately from Trunk, against the project's own environment. CI type-checks the whole backend on every backend change; to run it locally:

```sh
cd backend
uv run mypy --config-file ../.trunk/configs/mypy.ini .
```

**Failing to install and run the linter will result in a failed CI check, which won't allow us to merge your PR.**

## Test setup

### - Create the test user and database with root user

```sh
docker exec -i romm-db-dev mariadb -uroot -p<root password> < backend/romm_test/setup.sql
```

### - Run tests

_Migrations will be run automatically when running the tests._

```sh
cd backend
# path or test file can be passed as argument to test only a subset
uv run pytest [path/file]
# or run the following command to run all tests
# the -vv switch increases the verbosity of the output, providing more detailed information during test execution.
uv run pytest -vv
```
