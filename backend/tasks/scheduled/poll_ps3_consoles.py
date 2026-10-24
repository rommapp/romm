from pydantic import ValidationError

from handler.database import db_device_handler
from handler.redis_handler import async_cache
from handler.sync.ps3.console import PS3SyncConfig, is_lan_address, is_ps3
from handler.sync.ps3.ftp import probe
from handler.sync.ps3.sync_handler import enqueue_ps3_sync
from logger.logger import log
from models.device import SyncMode
from tasks.registry import POLL_PS3_CONSOLES_SPEC
from tasks.tasks import PeriodicTask

# The cron fires each minute, so a check expiring just after one waits for the next.
_INTERVAL_SLACK_SECONDS = 30


class PollPS3ConsolesTask(PeriodicTask):
    def __init__(self) -> None:
        super().__init__(POLL_PS3_CONSOLES_SPEC)

    async def run(self) -> None:
        if not self.spec.enabled:
            return

        devices = db_device_handler.get_all_devices_by_sync_mode(SyncMode.PUSH_PULL)
        for device in devices:
            address = device.ip_address
            if not is_ps3(device) or not device.sync_enabled or not address:
                continue
            if not is_lan_address(address):
                log.warning(
                    f"PS3 device {device.id} has no address on the local network"
                )
                continue
            try:
                config = PS3SyncConfig.of(device.sync_config)
            except ValidationError:
                log.warning(f"PS3 device {device.id} has invalid sync settings")
                continue

            # The key lives one interval, so the console is due once it expires.
            interval = config.poll_interval_minutes * 60 - _INTERVAL_SLACK_SECONDS
            if not await async_cache.set(
                f"romm:ps3_sync:{device.id}:checked", "1", nx=True, ex=interval
            ):
                continue

            if await probe(address, config.ftp_port) is None:
                log.debug(f"PS3 device {device.id} is not on the network")
                continue

            sync_session = enqueue_ps3_sync(device)
            log.info(
                f"PS3 device {device.id} is on the network, "
                f"queued sync session {sync_session.id}"
            )


poll_ps3_consoles_task = PollPS3ConsolesTask()
