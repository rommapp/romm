import sys

if sys.version_info >= (3, 12):
    from itertools import batched  # noqa: F401
else:
    from collections.abc import Iterable, Iterator
    from itertools import islice
    from typing import TypeVar

    T = TypeVar("T")

    def batched(iterable: Iterable[T], n: int) -> Iterator[tuple[T, ...]]:
        if n < 1:
            raise ValueError("n must be at least one")
        iterator = iter(iterable)
        while batch := tuple(islice(iterator, n)):
            yield batch
