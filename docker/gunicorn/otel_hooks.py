"""Gunicorn config that starts OpenTelemetry in each worker after it forks.

Starting it in the master instead would hand every worker the master's pid,
process metrics and resource, so their series would overwrite each other.
"""


def post_fork(server: object, worker: object) -> None:
    from opentelemetry.instrumentation.auto_instrumentation import initialize

    initialize()
