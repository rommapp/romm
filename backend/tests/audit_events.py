from handler.database import db_audit_event_handler
from handler.database.audit_events_handler import AuditEventFilters
from models.audit_event import AuditEvent


def recorded_events() -> list[AuditEvent]:
    """Every audit event recorded so far, newest first."""
    rows, _, _ = db_audit_event_handler.get_events(
        AuditEventFilters(), limit=200, offset=0
    )
    return [event for event, _ in rows]
