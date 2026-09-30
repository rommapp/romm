"""Whether anything is actually listening on the install queue.

Enqueueing a job nobody consumes leaves the session stuck "installing" (or
"streaming") forever: nothing ever touches its RQ job, so there's no natural
path to a FAILED state and the client polls indefinitely. Checked before
enqueueing instead of leaving that to fail silently — a misconfigured
deployment (install-sandbox worker not running) should say so immediately,
not hang.
"""

from __future__ import annotations

from rq import worker_registration

from handler.redis_handler import install_queue


def has_install_worker() -> bool:
    """True if at least one worker is currently registered on the install queue.

    Queries the queue-scoped registry set directly (``rq:workers:install``,
    via ``worker_registration.get_keys``), not each worker's own metadata
    hash: RQ's periodic heartbeat only ever refreshes that hash's
    ``last_heartbeat`` field, so a worker whose key briefly expired between
    two heartbeats (its TTL is tied to the currently running job's timeout,
    and our install jobs run long) comes back with everything else,
    including ``queues``, missing - looking dead to ``Worker.queue_names()``
    while it is, in fact, still very much alive and listening. Caught live:
    a worker that had been up for 44 minutes reported unavailable here
    despite actively processing jobs the whole time.
    """
    return bool(worker_registration.get_keys(queue=install_queue))
