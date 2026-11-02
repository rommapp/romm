from starlette.datastructures import FormData


def keep_empty_string(form: FormData, name: str, value: str | None) -> str | None:
    """Return "" when the client submitted the field empty, since FastAPI parses an
    empty form value as missing and clients send one to clear a field.
    """
    return "" if form.get(name) == "" else value
