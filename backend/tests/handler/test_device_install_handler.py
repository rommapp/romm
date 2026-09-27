import pytest

from endpoints.responses.device_install import InstallRequestSchema, InstallStatus
from handler.device_install_handler import (
    DeviceInstallHandler,
    InstallTransitionError,
)
from handler.redis_handler import as_text, async_cache, sync_cache

TWO_DAYS = 2 * 24 * 60 * 60
OUTCOMES = [
    InstallStatus.DONE,
    InstallStatus.ALREADY_INSTALLED,
    InstallStatus.FAILED,
]


@pytest.fixture(autouse=True)
def clear_cache():
    sync_cache.flushall()
    yield
    sync_cache.flushall()


@pytest.fixture
def handler() -> DeviceInstallHandler:
    return DeviceInstallHandler(ttl_days=2)


async def _create(
    handler: DeviceInstallHandler, device_id: str = "dev-1", rom_id: int = 7
) -> InstallRequestSchema:
    request, created = await handler.create(
        user_id=1, device_id=device_id, rom_id=rom_id, file_ids=[10, 11]
    )
    assert created
    return request


async def _taken(
    handler: DeviceInstallHandler, device_id: str = "dev-1", rom_id: int = 7
) -> InstallRequestSchema:
    request = await _create(handler, device_id, rom_id)
    await handler.claim(device_id)
    return request


async def _active_id(rom_id: int) -> str | None:
    value = await async_cache.get(f"install:active:1:dev-1:{rom_id}")
    return None if value is None else as_text(value)


async def _assert_gone(request: InstallRequestSchema) -> None:
    assert not await async_cache.exists(f"install:req:{request.id}")
    assert not await async_cache.exists(
        f"install:active:{request.user_id}:{request.device_id}:{request.rom_id}"
    )
    assert not await async_cache.sismember(
        f"install:device:{request.device_id}", request.id
    )
    assert not await async_cache.sismember(
        f"install:rom:{request.user_id}:{request.rom_id}", request.id
    )


class TestLifecycle:
    async def test_a_new_request_is_listed_for_its_device_and_its_rom(self, handler):
        request = await _create(handler)

        assert request.status == InstallStatus.PENDING
        assert [r.id for r in await handler.list_for_device("dev-1")] == [request.id]
        assert await handler.list_for_device("dev-2") == []
        assert [r.id for r in await handler.list_for_rom(1, 7)] == [request.id]
        assert await handler.get(request.id) == request

    async def test_a_live_request_expires_after_the_configured_days(self, handler):
        request = await _create(handler)

        for key in (
            f"install:req:{request.id}",
            "install:device:dev-1",
            "install:rom:1:7",
            "install:active:1:dev-1:7",
        ):
            assert 0 < await async_cache.ttl(key) <= TWO_DAYS

    async def test_an_unlimited_ttl_keeps_a_live_request(self):
        handler = DeviceInstallHandler(ttl_days=0)
        request = await _taken(handler)

        assert await async_cache.ttl(f"install:req:{request.id}") == -1

    @pytest.mark.parametrize("outcome", OUTCOMES)
    async def test_a_report_ends_a_taken_request_and_deletes_it(self, handler, outcome):
        request = await _taken(handler)

        ended = await handler.report(request.id, outcome, "no space")

        assert (ended.id, ended.status, ended.reason) == (
            request.id,
            outcome,
            "no space",
        )
        await _assert_gone(request)
        assert await handler.list_for_device("dev-1") == []

    async def test_a_pending_request_cannot_be_reported(self, handler):
        request = await _create(handler)

        with pytest.raises(InstallTransitionError):
            await handler.report(request.id, InstallStatus.DONE, None)

        stored = await handler.get(request.id)
        assert stored is not None and stored.status == InstallStatus.PENDING

    @pytest.mark.parametrize("claim", [False, True])
    async def test_a_live_request_can_be_cancelled(self, handler, claim):
        request = await (_taken if claim else _create)(handler)

        cancelled = await handler.cancel(request.id)

        assert cancelled.status == InstallStatus.CANCELLED
        await _assert_gone(request)

    async def test_a_repeated_report_finds_nothing(self, handler):
        request = await _taken(handler)
        await handler.report(request.id, InstallStatus.DONE, None)

        with pytest.raises(KeyError):
            await handler.report(request.id, InstallStatus.DONE, None)

    async def test_a_missing_request_is_a_key_error(self, handler):
        with pytest.raises(KeyError):
            await handler.cancel("gone")

    async def test_ending_leaves_another_requests_dedupe_key_alone(self, handler):
        request = await _create(handler)
        await async_cache.set("install:active:1:dev-1:7", "other")

        await handler.cancel(request.id)

        assert await _active_id(7) == "other"

    async def test_an_expired_request_drops_out_of_every_list(self, handler):
        request = await _create(handler)
        await async_cache.delete(f"install:req:{request.id}")

        assert await handler.list_for_device("dev-1") == []
        assert await handler.list_for_rom(1, 7) == []
        assert not await async_cache.sismember("install:device:dev-1", request.id)


class TestEndRace:
    async def test_a_cancel_between_the_read_and_the_commit_wins(self, mocker, handler):
        request = await _taken(handler)
        real_read = handler._read
        cancelled_once = False

        async def read_then_cancel(client, request_ids):
            nonlocal cancelled_once
            current = await real_read(client, request_ids)
            if not cancelled_once:
                cancelled_once = True
                await async_cache.delete(f"install:req:{request.id}")
            return current

        mocker.patch.object(handler, "_read", side_effect=read_then_cancel)

        with pytest.raises(KeyError):
            await handler.report(request.id, InstallStatus.DONE, None)


class TestClaim:
    async def test_takes_and_returns_every_pending_request(self, handler):
        first = await _create(handler, rom_id=7)
        second = await _create(handler, rom_id=8)
        other_device = await _create(handler, device_id="dev-2", rom_id=7)

        claim = await handler.claim("dev-1")

        assert [r.id for r in claim.taken] == [first.id, second.id]
        assert claim.newly_taken == claim.taken
        assert {r.status for r in claim.taken} == {InstallStatus.TAKEN}
        stored = await handler.get(first.id)
        assert stored is not None and stored.status == InstallStatus.TAKEN
        untouched = await handler.get(other_device.id)
        assert untouched is not None and untouched.status == InstallStatus.PENDING

    async def test_a_second_claim_returns_the_taken_requests_again(self, handler):
        request = await _create(handler)
        first = await handler.claim("dev-1")

        again = await handler.claim("dev-1")

        assert again.taken == first.taken
        assert [r.id for r in again.taken] == [request.id]
        assert again.newly_taken == []

    async def test_returns_earlier_and_new_requests_oldest_first(self, handler):
        earlier = await _taken(handler, rom_id=7)
        later = await _create(handler, rom_id=8)

        claim = await handler.claim("dev-1")

        assert [r.id for r in claim.taken] == [earlier.id, later.id]
        assert [r.id for r in claim.newly_taken] == [later.id]

    async def test_a_reported_request_stops_coming_back(self, handler):
        request = await _taken(handler)
        await handler.report(request.id, InstallStatus.DONE, None)

        assert await handler.claim("dev-1") == ([], [])

    async def test_renews_only_the_dedupe_keys_its_requests_still_own(self, handler):
        first = await _create(handler, rom_id=7)
        second = await _create(handler, rom_id=8)
        await async_cache.set("install:active:1:dev-1:7", "other")

        claim = await handler.claim("dev-1")

        assert [r.id for r in claim.newly_taken] == [first.id, second.id]
        assert await _active_id(7) == "other"
        assert await _active_id(8) == second.id
        assert 0 < await async_cache.ttl("install:active:1:dev-1:8") <= TWO_DAYS

    @pytest.mark.parametrize("with_pending", [False, True])
    async def test_drops_expired_ids_from_the_device_index(self, handler, with_pending):
        expired = await _create(handler, rom_id=7)
        await async_cache.delete(f"install:req:{expired.id}")
        if with_pending:
            await _create(handler, rom_id=8)

        await handler.claim("dev-1")

        assert not await async_cache.sismember("install:device:dev-1", expired.id)

    async def test_leaves_cancelled_requests_alone(self, handler):
        request = await _create(handler)
        await handler.cancel(request.id)

        assert await handler.claim("dev-1") == ([], [])

    async def test_a_cancel_between_the_read_and_the_commit_is_never_returned(
        self, mocker, handler
    ):
        request = await _create(handler)
        real_read = handler._read
        cancelled_once = False

        async def read_then_cancel(client, request_ids):
            nonlocal cancelled_once
            current = await real_read(client, request_ids)
            if not cancelled_once:
                cancelled_once = True
                await handler.cancel(request.id)
            return current

        mocker.patch.object(handler, "_read", side_effect=read_then_cancel)

        claim = await handler.claim("dev-1")

        assert claim == ([], [])
        assert await handler.get(request.id) is None


class TestDiscardForDevice:
    async def test_drops_every_live_request_of_the_device(self, handler):
        pending = await _create(handler, rom_id=7)
        taken = await _taken(handler, rom_id=8)
        other_device = await _create(handler, device_id="dev-2", rom_id=7)

        await handler.discard_for_device("dev-1")

        await _assert_gone(pending)
        await _assert_gone(taken)
        assert not await async_cache.exists("install:device:dev-1")
        assert [r.id for r in await handler.list_for_rom(1, 7)] == [other_device.id]

    async def test_a_device_without_requests_is_a_no_op(self, handler):
        await handler.discard_for_device("dev-1")

        assert not await async_cache.exists("install:device:dev-1")

    async def test_a_request_created_during_the_discard_stays_findable(
        self, mocker, handler
    ):
        list_for_device = handler.list_for_device
        late: list[InstallRequestSchema] = []

        async def list_then_create(device_id: str) -> list[InstallRequestSchema]:
            listed = await list_for_device(device_id)
            late.append(await _create(handler, rom_id=9))
            return listed

        patched = mocker.patch.object(
            handler, "list_for_device", side_effect=list_then_create
        )
        await handler.discard_for_device("dev-1")
        mocker.stop(patched)

        assert [r.id for r in await handler.list_for_device("dev-1")] == [late[0].id]
        await handler.discard_for_device("dev-1")
        await _assert_gone(late[0])

    async def test_a_broker_failure_leaves_the_device_deletion_standing(
        self, mocker, handler
    ):
        mocker.patch.object(
            handler, "list_for_device", side_effect=ConnectionError("redis")
        )

        await handler.discard_for_device("dev-1")


class TestDedupe:
    @pytest.mark.parametrize("claim", [False, True])
    async def test_a_second_create_returns_the_live_request(self, handler, claim):
        first = await (_taken if claim else _create)(handler)

        second, created = await handler.create(
            user_id=1, device_id="dev-1", rom_id=7, file_ids=[10]
        )

        assert not created
        assert second.id == first.id
        assert len(await handler.list_for_device("dev-1")) == 1

    async def test_each_device_gets_its_own_request(self, handler):
        first = await _create(handler, device_id="dev-1")
        second = await _create(handler, device_id="dev-2")

        assert first.id != second.id

    @pytest.mark.parametrize("outcome", [*OUTCOMES, InstallStatus.CANCELLED])
    async def test_an_ended_request_frees_the_rom_for_a_new_one(self, handler, outcome):
        first = await _taken(handler)
        if outcome == InstallStatus.CANCELLED:
            await handler.cancel(first.id)
        else:
            await handler.report(first.id, outcome, None)

        second = await _create(handler)

        assert second.id != first.id
        assert await _active_id(7) == second.id
