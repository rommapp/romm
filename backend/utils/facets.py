from collections.abc import Mapping


def facet_names(values: object) -> list[str]:
    """Clean names from a facet column, skipping entries that carry none."""
    # The raw-metadata form stores JSON unvalidated, so a column can hold
    # {id, name} objects, bare ids, or a scalar where a list belongs.
    if isinstance(values, str):
        values = [values]
    elif not isinstance(values, (list, tuple)):
        return []
    names: list[str] = []
    for value in values:
        name = value.get("name") if isinstance(value, Mapping) else value
        if isinstance(name, str) and (cleaned := name.strip()):
            names.append(cleaned)
    return names
