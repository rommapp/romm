# romm

## Project Setup for development

### Create python virtualenv

```sh
python3 -m venv backend/venv/romm
```

### Activate romm virtualenv

```sh
source backend/venv/romm/bin/activate
```

### Install venv dependencies

```sh
pip install -r backend/dependencies/requirements.txt
```

### Create environment variables file with the following variables

```sh
touch envs.env

# IGDB auth
CLIENT_ID=""
CLIENT_SECRET=""

# STEAMGRIDDB API KEY
STEAMGRIDDB_API_KEY=""

# Library path
LIBRARY_PATH="library_path/"

# DB related config
ROMM_DB_HOST=""
ROMM_DB_PORT=
ROMM_DB_ROOT_PASSWD=""
ROMM_DB_USER=""
ROMM_DB_PASSWD=""
ROMM_DB_CONFIG_PATH=""
```

### Export environment variables

```sh
export $(cat envs.env | xargs)
```

### Create mariadb docker container

```sh
docker-compose up -d (to your docker-compose file for run mariadb)
```

### Install node.js dependencies

```sh
npm install
```

## Project Testing

### Activate romm virtualenv

```sh
source backend/venv/romm/bin/activate
```

### Export environment variables

```sh
export $(cat envs.env | xargs)
```

### Start backend API

```sh
python3 backend/src/main.py
```

### Start frontend (compile and hot-reload)

```sh
npm run dev
```
