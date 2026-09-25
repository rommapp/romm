from datetime import datetime, timedelta, timezone

from handler.database import db_audit_event_handler, db_device_handler
from handler.database.audit_events_handler import AuditEventFilters
from models.audit_event import AuditAction, AuditActorKind, AuditCategory, AuditEvent
from models.device import Device
from models.rom import Rom
from models.user import User


def _add(minutes_ago: int = 0, **overrides) -> AuditEvent:
    event = AuditEvent(
        **{
            "occurred_at": datetime.now(timezone.utc) - timedelta(minutes=minutes_ago),
            "actor_kind": AuditActorKind.SYSTEM,
            "action": AuditAction.ROM_EDIT,
            "data": {},
            **overrides,
        }
    )
    db_audit_event_handler.add_events([event])
    return event


def _ids(filters: AuditEventFilters) -> list[int]:
    rows, _, _ = db_audit_event_handler.get_events(filters, limit=50, offset=0)
    return [event.id for event, _ in rows]


class TestHiddenTargets:
    def test_drops_events_on_roms_of_a_hidden_platform(self, rom: Rom):
        on_hidden = _add(target_type="rom", target_id=str(rom.id))
        elsewhere = _add(target_type="rom", target_id="999999")

        ids = _ids(AuditEventFilters(hidden_platform_ids={rom.platform_id}))

        assert on_hidden.id not in ids
        assert elsewhere.id in ids

    def test_drops_events_on_hidden_roms_and_platforms_only(self):
        hidden_rom = _add(target_type="rom", target_id="7")
        visible_rom = _add(target_type="rom", target_id="8")
        hidden_platform = _add(target_type="platform", target_id="7")
        no_target = _add()

        ids = _ids(AuditEventFilters(hidden_rom_ids={7}, hidden_platform_ids={7}))

        assert hidden_rom.id not in ids
        assert hidden_platform.id not in ids
        assert set(ids) == {visible_rom.id, no_target.id}


class TestCategories:
    def test_a_category_stands_for_its_actions(self):
        login = _add(action=AuditAction.AUTH_LOGIN)
        _add(action=AuditAction.ROM_EDIT)

        assert _ids(AuditEventFilters(categories=[AuditCategory.SECURITY])) == [
            login.id
        ]

    def test_actions_outside_the_category_match_nothing(self):
        _add(action=AuditAction.ROM_EDIT)

        filters = AuditEventFilters(
            actions=[AuditAction.ROM_EDIT], categories=[AuditCategory.SECURITY]
        )
        assert _ids(filters) == []


def test_joins_the_device_name(admin_user: User):
    db_device_handler.add_device(
        Device(id="dev-1", user_id=admin_user.id, name="Steam Deck")
    )
    _add(device_id="dev-1")
    _add(device_id="gone")

    rows, total, _ = db_audit_event_handler.get_events(
        AuditEventFilters(), limit=50, offset=0
    )

    assert total == 2
    assert sorted(name or "" for _, name in rows) == ["", "Steam Deck"]


class TestDeleteBatchBefore:
    def test_deletes_only_older_events_up_to_the_batch_size(self):
        old = [_add(minutes_ago=60 * 24 * 100) for _ in range(3)]
        recent = _add(minutes_ago=5)
        cutoff = datetime.now(timezone.utc) - timedelta(days=90)

        first = db_audit_event_handler.delete_batch_before(cutoff, batch_size=2)
        second = db_audit_event_handler.delete_batch_before(cutoff, batch_size=2)
        third = db_audit_event_handler.delete_batch_before(cutoff, batch_size=2)

        assert (first, second, third) == (2, 1, 0)
        assert _ids(AuditEventFilters()) == [recent.id]
        assert all(event.id not in _ids(AuditEventFilters()) for event in old)
