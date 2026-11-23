"""A failure callback for test_rq_worker; it records which process ran it."""

import os

MARKER_ENV = "ROMM_TEST_KILLED_HORSE_MARKER"


def record(job, connection, exc_type, exc_value, traceback) -> None:
    with open(os.environ[MARKER_ENV], "w") as marker:
        marker.write(str(os.getpid()))
