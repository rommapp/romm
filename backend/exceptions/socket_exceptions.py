class ScanStoppedException(Exception): ...


class ScanInFlightException(Exception):
    """A library scan is already queued or running, so another one is refused."""
