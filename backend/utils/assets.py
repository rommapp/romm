from fastapi import HTTPException, status

from models.assets import ASSET_LABEL_MAX_LENGTH, ASSET_LABELS_MAX


def normalize_asset_labels(labels: list[str]) -> list[str]:
    """Trim, drop blanks and de-duplicate case-insensitively, keeping order.

    Raises:
        HTTPException: if a label is too long or there are too many of them.
    """
    cleaned: list[str] = []
    seen: set[str] = set()
    for label in labels:
        trimmed = label.strip()
        if not trimmed or trimmed.casefold() in seen:
            continue
        if len(trimmed) > ASSET_LABEL_MAX_LENGTH:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Labels cannot exceed {ASSET_LABEL_MAX_LENGTH} characters",
            )
        seen.add(trimmed.casefold())
        cleaned.append(trimmed)

    if len(cleaned) > ASSET_LABELS_MAX:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"An asset cannot carry more than {ASSET_LABELS_MAX} labels",
        )
    return cleaned
