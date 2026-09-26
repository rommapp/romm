# RomM backend

## Commands (`cd backend`)

```bash
uv sync --all-extras --dev          # install
uv run main.py              # run (migrations auto-apply)
uv run pytest <path/file>           # test - affected files only, NEVER the whole suite
uv run alembic revision --autogenerate -m "msg"   # new migration (then HAND-REVIEW)
uv run alembic upgrade head         # apply migrations
```
