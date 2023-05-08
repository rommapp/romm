## Setting up the backend

### Copy envs.template to envs.env and fill the variables

```sh
cp env.template .env
```

### Install python dependencies

You'll need poetry installed

https://python-poetry.org/docs/#installing-with-the-official-installer

Then initialize the virtual environment and install the dependencies

```sh
poetry shell
poetry install
```

### Spin up mariadb in docker

```sh
docker-compose up -d
```

### Run the backend

```sh
python3 backend/main.py
```

## Setting up the frontend

### Install node.js dependencies

```sh
cd frontend
npm install
```

### Run the frontend

```sh
npm run dev
```
