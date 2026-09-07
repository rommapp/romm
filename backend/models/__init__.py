import importlib
import pkgutil


def load_all_models() -> None:
    """Import every module under `models/` so `BaseModel.metadata` is complete.

    A table missing from the metadata makes alembic autogenerate propose
    dropping it, so both `alembic/env.py` and the drift test load them all.
    """
    for module in pkgutil.iter_modules(__path__):
        importlib.import_module(f"{__name__}.{module.name}")
