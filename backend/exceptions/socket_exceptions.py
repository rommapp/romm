class ScanStoppedException(Exception): ...


class ScanInFlightException(Exception):
    """A library scan is already queued or running, so another one is refused."""


class NoScanWorkerException(Exception):
    """No worker listens on the scan queue, so a queued scan would never start."""
