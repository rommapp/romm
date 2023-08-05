# Environment setup

## Mocking RomM structure

### - Create the mock structure with at least one rom and empty config for manual testing

```sh
mkdir -p romm_mock/library/roms/switch
touch romm_mock/library/roms/switch/metroid.xci
mkdir -p romm_mock/resources
touch romm_mock/config.yml
```

## Setting up the backend

### - Copy env.template to .env and fill the variables

```sh
cp env.template .env
```

### - Install python dependencies

You'll need poetry installed

https://python-poetry.org/docs/#installing-with-the-official-installer

Then initialize the virtual environment and install the dependencies

```sh
poetry shell
# Fix disable parallel installation stuck: $> poetry config experimental.new-installer false
# Fix Loading macOS/linux stuck: $> export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
# Fix mariadb install on linux: $> sudo apt install libmariadb3 libmariadb-dev
# Fix mariadb connector/c >= 3.3.1: https://mariadb.com/docs/skysql-previous-release/connect/programming-languages/c/install/#Installation_via_Package_Repository_(Linux)
poetry install
```

### - Spin up mariadb in docker

```sh
docker-compose up -d
```

### - Run the backend

*__*Migrations will be run automatically when running the backend.__*

```sh
cd backend
python main.py
```


### - Start a worker

```sh
cd backend
python worker.py
```

## Setting up the frontend

### - Install node.js dependencies

```sh
cd frontend
# npm version >= 9 needed
npm install
```

### - Create symlink to library and resources
```sh
mkdir assets/romm
ln -s ../../../romm_mock/library assets/romm/library
ln -s ../../../romm_mock/resources assets/romm/resources
```

### - Run the frontend

```sh
npm run dev
```

# Test setup

### - Create the test user and database with root user

```sh
docker exec -i mariadb mysql -u root -p<root password> < backend/romm_test/setup.sql    # for amd images
docker exec -i mariadb mariadb -u root -p<root password> < backend/romm_test/setup.sql  # for arm images
```

### - Run tests

*__*Migrations will be run automatically when running the tests.__*

```sh
cd backend
# path or test file can be passed as argument to test only a subset
pytest [path/file]
```
