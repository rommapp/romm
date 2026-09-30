import handler.install.queue_status as queue_status


class TestHasInstallWorker:
    """Regression coverage for a real bug: this used to ask each worker's
    own Worker.queue_names(), which RQ only populates on a fresh
    register_birth() - the periodic heartbeat during a long-running job
    only ever refreshes that key's last_heartbeat field, so a key that
    happened to fully expire between two heartbeats came back missing
    queues (and everything else) even though the worker was still alive
    and listening. Caught live: a worker up 44 minutes, still actively
    processing install jobs, reported as no worker connected. The
    queue-scoped registry set (rq:workers:<queue>) doesn't have this
    problem - it's a plain SADD/SREM membership set, not a heartbeat-
    refreshed hash - so has_install_worker reads that instead.
    """

    def test_true_when_the_registry_set_has_a_member(self, monkeypatch):
        monkeypatch.setattr(
            queue_status.worker_registration, "get_keys", lambda queue: {"a-worker"}
        )

        assert queue_status.has_install_worker() is True

    def test_false_when_the_registry_set_is_empty(self, monkeypatch):
        monkeypatch.setattr(
            queue_status.worker_registration, "get_keys", lambda queue: set()
        )

        assert queue_status.has_install_worker() is False

    def test_true_even_when_a_member_workers_own_hash_is_degraded(self, monkeypatch):
        # The exact scenario caught live: the worker is still a member of
        # the queue's registry set even though its own metadata hash has
        # decayed to just last_heartbeat - has_install_worker never reads
        # that hash at all, so it isn't fooled by it either.
        monkeypatch.setattr(
            queue_status.worker_registration,
            "get_keys",
            lambda queue: {"a-worker-with-a-bare-heartbeat-only-hash"},
        )

        assert queue_status.has_install_worker() is True
