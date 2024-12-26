from typing import Callable

from py7zr import Py7zIO, WriterFactory


class CallbackIO(Py7zIO):
    """Py7zIO implementation that calls a callback on write and read."""

    def __init__(
        self,
        filename: str,
        on_write: Callable[[bytes | bytearray], None],
        on_read: Callable[[int | None], bytes],
    ):
        self.filename = filename
        self.on_write = on_write
        self.on_read = on_read
        self._size = 0

    def write(self, s: bytes | bytearray) -> int:
        length = len(s)
        self._size += length
        self.on_write(s)
        return length

    def read(self, size: int | None = None) -> bytes:
        return self.on_read(size)

    def seek(self, offset: int, whence: int = 0) -> int:
        return 0

    def flush(self) -> None: ...

    def size(self) -> int:
        return self._size


class CallbackIOFactory(WriterFactory):
    """WriterFactory implementation that creates CallbackIO instances."""

    def __init__(
        self,
        on_write: Callable[[bytes | bytearray], None],
        on_read: Callable[[int | None], bytes],
    ):
        self.products: dict[str, CallbackIO] = {}
        self.on_write = on_write
        self.on_read = on_read

    def create(self, filename: str) -> CallbackIO:
        product = CallbackIO(
            filename=filename, on_write=self.on_write, on_read=self.on_read
        )
        self.products[filename] = product
        return product

    def get(self, filename: str) -> Py7zIO:
        return self.products[filename]
