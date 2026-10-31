"""Re-derive ROM sort keys when the articles `sorting.articles` names change."""

import json

from handler.database import db_rom_handler
from handler.redis_handler import sync_cache
from logger.logger import log
from models.rom import ARTICLES, compute_name_sort_key, sort_articles
from tasks.registry import RECOMPUTE_NAME_SORT_KEYS_SPEC
from tasks.tasks import Task

APPLIED_SORT_ARTICLES_KEY = "romm:sort_articles"
PAGE_SIZE = 1000


def applied_sort_articles() -> tuple[str, ...]:
    """The articles the stored sort keys were derived with."""
    stored = sync_cache.get(APPLIED_SORT_ARTICLES_KEY)
    # Keys stored with no list recorded were derived with every LaunchBox article.
    return tuple(json.loads(stored)) if stored else ARTICLES


class RecomputeNameSortKeysTask(Task):
    def __init__(self) -> None:
        super().__init__(RECOMPUTE_NAME_SORT_KEYS_SPEC)

    async def run(self) -> dict[str, int]:
        previous = applied_sort_articles()
        current = sort_articles()
        scanned = replaced = 0
        last_id = 0
        while batch := db_rom_handler.get_name_sort_keys_after_id(last_id, PAGE_SIZE):
            replacements: dict[int, tuple[str | None, str]] = {}
            for rom_id, name, sort_key in batch:
                last_id = rom_id
                scanned += 1
                # A key other than the derived one is a custom sort key.
                if sort_key is not None and sort_key != compute_name_sort_key(
                    name, articles=previous
                ):
                    continue
                derived = compute_name_sort_key(name, articles=current)
                if derived != sort_key:
                    replacements[rom_id] = (sort_key, derived)
            if replacements:
                replaced += db_rom_handler.replace_name_sort_keys(replacements)

        sync_cache.set(APPLIED_SORT_ARTICLES_KEY, json.dumps(current))
        log.info(f"{self.spec.title} complete: scanned={scanned}, replaced={replaced}")
        return {"roms_scanned": scanned, "sort_keys_replaced": replaced}


recompute_name_sort_keys_task = RecomputeNameSortKeysTask()
