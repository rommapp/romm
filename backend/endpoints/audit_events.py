from datetime import datetime
from typing import Annotated

from fastapi import Query, Request
from fastapi_pagination import resolve_params
from fastapi_pagination.limit_offset import LimitOffsetParams
from pydantic import BaseModel

from decorators.auth import protected_route
from endpoints.responses.audit_event import AuditEventSchema
from endpoints.responses.base import TypedLimitOffsetPage
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.database import db_audit_event_handler
from handler.database.audit_events_handler import AuditEventFilters
from models.audit_event import AuditCategory, actions_in
from utils.router import APIRouter

router = APIRouter(prefix="/audit-events", tags=["audit"])


class AuditLimitOffsetParams(LimitOffsetParams):
    limit: int = Query(50, ge=1, le=200, description="Page size limit")
    offset: int = Query(0, ge=0, description="Page offset")


class AuditPage[T: BaseModel](TypedLimitOffsetPage[T]):
    __params_type__ = AuditLimitOffsetParams


@protected_route(router.get, "", [Scope.ME_READ])
def get_audit_events(
    request: Request,
    actor_id: Annotated[
        list[int] | None,
        Query(
            description="Only these users' events; ignored unless the caller is an admin."
        ),
    ] = None,
    action: Annotated[
        list[str] | None, Query(description="Only these actions.")
    ] = None,
    category: Annotated[
        list[AuditCategory] | None, Query(description="Only actions in these groups.")
    ] = None,
    target_type: Annotated[str | None, Query()] = None,
    target_id: Annotated[str | None, Query()] = None,
    since: Annotated[datetime | None, Query(description="Inclusive.")] = None,
    until: Annotated[datetime | None, Query(description="Exclusive.")] = None,
    search: Annotated[
        str | None, Query(description="Substring match on the actor or target name.")
    ] = None,
    max_id: Annotated[
        int | None,
        Query(description="Pins later pages to the events the first one saw."),
    ] = None,
) -> AuditPage[AuditEventSchema]:
    """The audit log, newest first: everyone's for an admin, the caller's own otherwise."""
    perms = get_permissions(request)
    params: AuditLimitOffsetParams = resolve_params()

    # An admin's token scoped below users.read must not read other users' history.
    sees_everyone = perms.is_admin and Scope.USERS_READ in request.auth.scopes

    actions: set[str] | None = set(action) if action else None
    if category:
        in_categories: set[str] = {a for c in category for a in actions_in(c)}
        actions = in_categories if actions is None else actions & in_categories

    rows, total = db_audit_event_handler.get_events(
        AuditEventFilters(
            actor_ids=(actor_id or None) if sees_everyone else [request.user.id],
            actions=actions,
            target_type=target_type,
            target_id=target_id,
            since=since,
            until=until,
            max_id=max_id,
            search=search,
            hidden_rom_ids=frozenset() if perms.is_admin else perms.hidden_rom_ids,
            hidden_platform_ids=(
                frozenset() if perms.is_admin else perms.hidden_platform_ids
            ),
        ),
        limit=params.limit,
        offset=params.offset,
    )
    return AuditPage.create(
        [AuditEventSchema.from_row(event, device_name) for event, device_name in rows],
        params,
        total=total,
    )
