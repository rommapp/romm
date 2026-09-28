from datetime import datetime
from typing import Annotated

from fastapi import Depends, Query, Request
from pydantic import BaseModel, Field

from decorators.auth import protected_route
from endpoints.responses.audit_event import AuditEventSchema
from endpoints.responses.base import LimitOffsetPage, PageParams
from handler.auth.constants import Scope
from handler.auth.dependencies import get_permissions
from handler.database import db_audit_event_handler
from handler.database.audit_events_handler import AuditEventFilters
from models.audit_event import AuditCategory
from utils.router import APIRouter, as_query_dependency

router = APIRouter(prefix="/audit-events", tags=["audit"])


class AuditPageParams(PageParams):
    limit: int = Field(50, ge=1, le=200, description="Page size limit")


AUDIT_PAGE_QUERY = as_query_dependency(AuditPageParams)


class AuditPage[T: BaseModel](LimitOffsetPage[T]):
    # Rows are ordered by when they happened, not by id, so later pages pin to
    # the highest id rather than to the first row's.
    max_id: int | None = None


@protected_route(router.get, "", [Scope.ME_READ])
def get_audit_events(
    request: Request,
    params: Annotated[AuditPageParams, Depends(AUDIT_PAGE_QUERY)],
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
        str | None,
        Query(description="Substring match on the actor, target name or IP address."),
    ] = None,
    max_id: Annotated[
        int | None,
        Query(description="Pins later pages to the events the first one saw."),
    ] = None,
) -> AuditPage[AuditEventSchema]:
    """The audit log, newest first: everyone's for an admin, the caller's own otherwise."""
    perms = get_permissions(request)

    # An admin's token scoped below users.read must not read other users' history.
    sees_everyone = perms.is_admin and Scope.USERS_READ in request.auth.scopes

    rows, total, highest_id = db_audit_event_handler.get_events(
        AuditEventFilters(
            actor_ids=(actor_id or None) if sees_everyone else [request.user.id],
            actions=action or None,
            categories=category,
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
    return AuditPage(
        items=[
            AuditEventSchema.from_row(event, device_name) for event, device_name in rows
        ],
        total=total,
        limit=params.limit,
        offset=params.offset,
        max_id=highest_id,
    )
