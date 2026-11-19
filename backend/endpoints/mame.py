from typing import TypedDict

from anyio import open_file
from fastapi import File, HTTPException, Request, UploadFile, status

from decorators.auth import protected_route
from endpoints.responses import TaskExecutionResponse
from endpoints.tasks import _build_task_execution_response
from handler.audit_handler import AuditTarget, record
from handler.auth.constants import Scope
from handler.metadata.mame_index import MameIndexInfo, get_index_info
from handler.redis_handler import has_live_worker, low_prio_queue
from models.audit_event import AuditAction, AuditTargetType
from tasks.registry import UPDATE_MAME_INDEX_SPEC, enqueue_task, get_active_task_job
from tasks.scheduled.update_mame_index import MAME_UPLOAD_PATH
from utils.router import APIRouter
from utils.uploads import check_asset_upload_size

router = APIRouter(prefix="/mame", tags=["mame"])

TASK_NAME = "update_mame_index"
UPLOAD_CHUNK_SIZE = 1024 * 1024


class MameIndexStatus(TypedDict):
    loaded: bool
    info: MameIndexInfo | None
    updating: bool


@protected_route(router.get, "/index", [Scope.TASKS_RUN])
async def get_mame_index(request: Request) -> MameIndexStatus:
    """What the loaded MAME index holds, and whether an update is under way."""
    info = await get_index_info()
    return MameIndexStatus(
        loaded=info is not None,
        info=info,
        updating=get_active_task_job(TASK_NAME) is not None,
    )


@protected_route(router.post, "/index", [Scope.TASKS_RUN])
async def upload_mame_index(
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
) -> TaskExecutionResponse:
    """Load the MAME index from a `mame -listxml` file, or a zip holding one."""
    check_asset_upload_size(file, "MAME XML")
    if not has_live_worker(low_prio_queue):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="No task worker is listening, so the import cannot be queued",
        )
    if get_active_task_job(TASK_NAME) is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{UPDATE_MAME_INDEX_SPEC.title} is already queued or running",
        )

    MAME_UPLOAD_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with await open_file(MAME_UPLOAD_PATH, "wb") as target:
        while chunk := await file.read(UPLOAD_CHUNK_SIZE):
            await target.write(chunk)

    job = enqueue_task(
        TASK_NAME,
        queue=low_prio_queue,
        task_kwargs={"uploaded": True},
        run_by_user_id=request.user.id,
    )
    record(
        AuditAction.TASK_RUN,
        request,
        AuditTarget(AuditTargetType.TASK, TASK_NAME, UPDATE_MAME_INDEX_SPEC.title),
        {"job_id": job.id, "file": file.filename or ""},
    )
    return _build_task_execution_response(
        job, TASK_NAME, UPDATE_MAME_INDEX_SPEC.title
    )
