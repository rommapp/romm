## Create the mock structure with at least one rom

```sh
mkdir -p romm_mock/library/roms/switch
touch romm_mock/library/roms/switch/metroid.xci
mkdir -p romm_mock/resources
touch romm_mock/config.yml
```

## Setting up the backend

### Copy env.template to .env and fill the variables

```sh
cp env.template .env
```

### Install python dependencies

You'll need poetry installed

https://python-poetry.org/docs/#installing-with-the-official-installer

Then initialize the virtual environment and install the dependencies

```sh
poetry shell
# Fix disable parallel installation stuck: $> poetry config experimental.new-installer false
# Fix Loading macOS stuck: $> export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
poetry install
```

### Spin up mariadb in docker

```sh
docker-compose up -d
```

### Run the migrations

```sh
cd backend
alembic upgrade head
```

## And finally run the backend

```sh
python main.py
```

## Setting up the frontend

### Install node.js dependencies

```sh
cd frontend
npm install
```

### Create symlink to library and resources
```sh
mkdir assets/romm
ln -s ../../../romm_mock/library assets/romm/library
ln -s ../../../romm_mock/resources assets/romm/resources
```

### Run the frontend

```sh
npm run dev
```
