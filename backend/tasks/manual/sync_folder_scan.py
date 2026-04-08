"""Manual scan task for sync folders with unprocessed files.

This serves as a fallback for the file watcher, handling cases where
filesystem events are missed (e.g., server restart, NFS mounts).
Triggered on demand, not scheduled automatically.
"""

from typing import Any

from config import ENABLE_SYNC_FOLDER_WATCHER
from handler.database import db_device_handler
from handler.filesystem import fs_sync_handler
from logger.logger import log
from models.device import SyncMode
from tasks.tasks import Task, TaskType


class SyncFolderScanTask(Task):
    """Scan device sync folders for unprocessed incoming files."""

    def __init__(self) -> None:
        super().__init__(
            title="Sync Folder Scan",
            description="Scan device sync folders for new save files",
            task_type=TaskType.SYNC,
            enabled=ENABLE_SYNC_FOLDER_WATCHER,
            manual_run=True,
        )

    async def run(self, *args: Any, **kwargs: Any) -> dict:
        if not self.enabled:
            log.info("Sync folder scan not enabled, skipping")
            return {"status": "disabled"}

        # Get all file_transfer devices
        devices = db_device_handler.get_all_devices_by_sync_mode(SyncMode.FILE_TRANSFER)
        if not devices:
            log.info("No file_transfer devices found")
            return {"status": "no_devices"}

        total_files = 0
        for device in devices:
            if not device.sync_enabled:
                continue

            incoming_files = fs_sync_handler.list_incoming_files(device.id)
            if incoming_files:
                log.info(
                    f"Sync folder scan: found {len(incoming_files)} files "
                    f"for device {device.id}"
                )
                # Import here to avoid circular imports
                from sync_watcher import _process_device_incoming

                file_tuples = [
                    (f["platform_slug"], f["file_name"], f["full_path"])
                    for f in incoming_files
                ]
                _process_device_incoming(device.id, file_tuples)
                total_files += len(incoming_files)

        return {"status": "completed", "files_processed": total_files}


sync_folder_scan_task = SyncFolderScanTask()
