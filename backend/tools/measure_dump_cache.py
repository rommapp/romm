"""Measure what the metadata dump stores cost in a real valkey, encoded or not.

Imports the real LaunchBox and Switch TitleDB dumps twice over, once storing
plain JSON and once through `handler.dump_cache.encode`, and reports each
store's size, the exact compression ratio, and decode latency.

The record shapes and store keys mirror `tasks/scheduled/update_*.py`; the walk
lives here because a tool cannot import the task without standing up the whole
app. The folded-title index is keyed by a stand-in for `fold_title`, whose
output length (not its exact spelling) is what its size depends on.

Sizes come from `MEMORY USAGE <key> SAMPLES 0`, which walks every field. The
default of 5 samples extrapolates, and on a hash of this size it is wrong by
enough to make per-key figures disagree with `used_memory`.

The dump stores on the target server are dropped and rebuilt, and nothing else
on it is touched. It refuses a server holding anything else unless forced,
since a live RomM would have to re-import what it drops.

Usage:
    uv run tools/measure_dump_cache.py \
        --metadata-zip Metadata.zip --titledb US.en.json \
        --redis-url redis://localhost:6379
"""

import argparse
import json
import re
import statistics
import sys
import time
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any, Final

import redis
from defusedxml import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handler.dump_cache import COMPRESS_MIN_BYTES, decode, encode  # noqa: E402

# Mirrors the keys the two update tasks write.
DATABASE_ID_KEY: Final = "romm:launchbox_metadata_database_id"
NAME_KEY: Final = "romm:launchbox_metadata_name"
ALTERNATE_NAME_KEY: Final = "romm:launchbox_metadata_alternate_name"
FOLDED_NAME_KEY: Final = "romm:launchbox_metadata_folded_name"
IMAGE_KEY: Final = "romm:launchbox_metadata_image"
MAME_KEY: Final = "romm:launchbox_mame"
FILES_KEY: Final = "romm:launchbox_files"
PLATFORMS_KEY: Final = "romm:launchbox_platforms"
TITLEDB_KEY: Final = "romm:switch_titledb"
PRODUCT_ID_KEY: Final = "romm:switch_product_id"

# Every key this tool writes, and the only keys it is ever allowed to delete.
STORE_KEYS: Final[tuple[str, ...]] = (
    DATABASE_ID_KEY,
    NAME_KEY,
    ALTERNATE_NAME_KEY,
    FOLDED_NAME_KEY,
    IMAGE_KEY,
    MAME_KEY,
    FILES_KEY,
    PLATFORMS_KEY,
    TITLEDB_KEY,
    PRODUCT_ID_KEY,
)

# Mirrors GAME_IMAGE_FIELDS in the LaunchBox task.
GAME_IMAGE_FIELDS: Final[frozenset[str]] = frozenset({"FileName", "Type", "Region"})

WRITE_BATCH = 2000
NON_ALNUM = re.compile(r"[^a-z0-9]+")

Record = tuple[str, str, Any]


def fold_stand_in(title: str) -> str:
    """Approximate `fold_title`: same shape and length, not the same algorithm."""
    return NON_ALNUM.sub("", title.strip().lower())


def element_to_dict(elem: Any, fields: frozenset[str] | None = None) -> dict[str, Any]:
    return {
        child.tag: child.text for child in elem if fields is None or child.tag in fields
    }


def iter_elements(source: Any) -> Iterator[Any]:
    """Yield each top-level record, dropping it once the caller moves on."""
    ctx = ET.iterparse(source, events=("start", "end"))
    try:
        _, root = next(iter(ctx))
    except StopIteration:
        return

    depth = 0
    for event, elem in ctx:
        if event == "start":
            depth += 1
            continue
        depth -= 1
        if depth > 0:
            continue
        yield elem
        root.clear()


def iter_launchbox(metadata_zip: Path) -> Iterator[Record]:
    with zipfile.ZipFile(metadata_zip) as z:
        names = z.namelist()

        if "Platforms.xml" in names:
            with z.open("Platforms.xml") as f:
                for elem in iter_elements(f):
                    if elem.tag != "Platform":
                        continue
                    name = elem.find("Name")
                    if name is not None and name.text:
                        yield PLATFORMS_KEY, name.text.strip(), element_to_dict(elem)

        if "Metadata.xml" in names:
            with z.open("Metadata.xml") as f:
                image_id: str | None = None
                images: list[dict[str, Any]] = []

                for elem in iter_elements(f):
                    if elem.tag == "Game":
                        id_elem = elem.find("DatabaseID")
                        database_id = (
                            id_elem.text.strip()
                            if id_elem is not None and id_elem.text
                            else None
                        )
                        if database_id:
                            yield DATABASE_ID_KEY, database_id, element_to_dict(elem)

                        name_elem = elem.find("Name")
                        platform_elem = elem.find("Platform")
                        if (
                            database_id
                            and name_elem is not None
                            and name_elem.text
                            and platform_elem is not None
                            and platform_elem.text
                        ):
                            platform = platform_elem.text.strip()
                            title = name_elem.text.strip()
                            yield (
                                NAME_KEY,
                                f"{title.lower()}:{platform}",
                                database_id,
                            )
                            folded = fold_stand_in(title)
                            if folded:
                                yield (
                                    FOLDED_NAME_KEY,
                                    f"{folded}:{platform}",
                                    database_id,
                                )

                    elif elem.tag == "GameAlternateName":
                        alt = elem.find("AlternateName")
                        if alt is not None and alt.text:
                            yield (
                                ALTERNATE_NAME_KEY,
                                alt.text.strip().lower(),
                                element_to_dict(elem),
                            )

                    elif elem.tag == "GameImage":
                        id_elem = elem.find("DatabaseID")
                        if id_elem is None or not id_elem.text:
                            continue
                        current = id_elem.text.strip()
                        if image_id is not None and current != image_id:
                            yield IMAGE_KEY, image_id, images
                            images = []
                        image_id = current
                        images.append(element_to_dict(elem, GAME_IMAGE_FIELDS))

                if image_id is not None:
                    yield IMAGE_KEY, image_id, images

        if "Mame.xml" in names:
            with z.open("Mame.xml") as f:
                for elem in iter_elements(f):
                    if elem.tag != "MameFile":
                        continue
                    fn = elem.find("FileName")
                    if fn is not None and fn.text:
                        yield MAME_KEY, fn.text.strip(), element_to_dict(elem)

        if "Files.xml" in names:
            with z.open("Files.xml") as f:
                for elem in iter_elements(f):
                    if elem.tag != "File":
                        continue
                    fn = elem.find("FileName")
                    platform = elem.find("Platform")
                    if (
                        fn is not None
                        and fn.text
                        and platform is not None
                        and platform.text
                    ):
                        field = f"{fn.text.strip().lower()}:{platform.text.strip()}"
                        yield FILES_KEY, field, element_to_dict(elem)


def iter_titledb(titledb: Path) -> Iterator[Record]:
    data = json.loads(titledb.read_text())
    relevant = {k: v for k, v in data.items() if k and v}
    for title_id, entry in relevant.items():
        yield TITLEDB_KEY, title_id, entry
    for title_id, entry in relevant.items():
        product_id = entry.get("id")
        if product_id:
            yield PRODUCT_ID_KEY, product_id, title_id


def plain(value: Any) -> bytes:
    """What the stores held before this change."""
    return json.dumps(value).encode()


def load(client: redis.Redis, records: Iterator[Record], serialize: Any) -> None:
    """Write every record into the store its key names."""
    pipe = client.pipeline(transaction=False)
    queued = 0
    for key, field, value in records:
        pipe.hset(key, mapping={field: serialize(value)})
        queued += 1
        if queued >= WRITE_BATCH:
            pipe.execute()
            queued = 0
    if queued:
        pipe.execute()


def store_stats(client: redis.Redis) -> tuple[dict[str, int], dict[str, int]]:
    """Field count and total value bytes per store, read back off the hashes.

    Taken from the stores rather than tallied while writing, because the dump
    repeats a title on one platform and an alternate name across platforms, so
    several records land on one field and only the last of them survives.
    """
    counts: dict[str, int] = {}
    value_bytes: dict[str, int] = {}
    for key in STORE_KEYS:
        count = client.hlen(key)
        if not count:
            continue
        counts[key] = count
        value_bytes[key] = sum(
            len(value) for _, value in client.hscan_iter(key, count=1000)
        )
    return counts, value_bytes


def foreign_keys(client: redis.Redis) -> int:
    """How many keys on the server are not this tool's own stores."""
    owned = {key.encode() for key in STORE_KEYS}
    return sum(1 for key in client.scan_iter(count=1000) if key not in owned)


def clear_stores(client: redis.Redis) -> tuple[int, int]:
    """Drop only this tool's stores, returning usage without them.

    Deliberately not `flushall`: the URL can point at a live RomM instance,
    whose sessions and RQ queues share the database with these stores.

    Returns:
        The server's `used_memory` and `used_memory_rss` with the stores gone,
        each of which only ever offsets the same metric.
    """
    client.delete(*STORE_KEYS)
    info = client.info("memory")
    return int(info["used_memory"]), int(info["used_memory_rss"])


def measure(client: redis.Redis, keys: list[str]) -> tuple[dict[str, int], int, int]:
    sizes = {}
    for key in keys:
        # SAMPLES 0 walks every field rather than extrapolating from five.
        size = client.execute_command("MEMORY", "USAGE", key, "SAMPLES", 0)
        if size:
            sizes[key] = int(size)
    info = client.info("memory")
    return sizes, int(info["used_memory"]), int(info["used_memory_rss"])


def mb(value: float) -> str:
    return f"{value / 1024 / 1024:>8.1f}M"


def sweep_threshold(metadata_zip: Path, limit: int) -> None:
    """Total stored bytes at each candidate COMPRESS_MIN_BYTES, on real records."""
    import zstandard

    from handler.dump_cache import COMPRESSION_LEVEL

    compressor = zstandard.ZstdCompressor(level=COMPRESSION_LEVEL)
    sample: list[bytes] = []
    for _, _, value in iter_launchbox(metadata_zip):
        sample.append(plain(value))
        if len(sample) >= limit:
            break

    print(f"\nthreshold sweep over {len(sample):,} real records")
    print(f"{'min bytes':>10} {'stored':>10} {'ratio':>7} {'compressed':>11}")
    for threshold in (0, 64, 128, 192, 256, 384, 512, 1024, 1 << 30):
        total = 0
        compressed = 0
        for payload in sample:
            if len(payload) >= threshold:
                total += len(compressor.compress(payload))
                compressed += 1
            else:
                total += len(payload)
        raw = sum(len(p) for p in sample)
        label = "never" if threshold == 1 << 30 else f"{threshold}"
        print(
            f"{label:>10} {mb(total)} {raw / total:>6.2f}x "
            f"{compressed / len(sample):>10.0%}"
        )


def bench_decode(
    client: redis.Redis, key: str, rounds: int = 5
) -> tuple[float, float] | None:
    """Median `decode` latency, and mean stored size, on real stored records."""
    fields = client.hrandfield(key, 2000)
    if not fields:
        return None
    blobs = [b for b in client.hmget(key, fields) if b]
    if not blobs:
        return None

    times = []
    for _ in range(rounds):
        start = time.perf_counter()
        for blob in blobs:
            decode(blob)
        times.append((time.perf_counter() - start) / len(blobs) * 1e6)

    return statistics.median(times), statistics.mean(len(b) for b in blobs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-zip", type=Path, required=True)
    parser.add_argument("--titledb", type=Path)
    parser.add_argument("--redis-url", default="redis://localhost:6379")
    parser.add_argument(
        "--sweep",
        type=int,
        default=0,
        metavar="N",
        help="sweep the compression threshold over N records and exit",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="run even though the server holds data other than these stores",
    )
    parser.add_argument(
        "--only",
        choices=("plain", "encoded"),
        help="load one encoding and report it, for reading RSS off a server "
        "started fresh for this pass",
    )
    args = parser.parse_args()

    if args.sweep:
        sweep_threshold(args.metadata_zip, args.sweep)
        return 0

    client = redis.Redis.from_url(args.redis_url)

    foreign = foreign_keys(client)
    if foreign and not args.force:
        print(
            f"{args.redis_url} holds {foreign:,} key(s) outside the metadata dump "
            "stores, so it looks like a live instance. This tool drops and rebuilds "
            "the dump stores, which a running RomM would then have to re-import. "
            "Point it at a disposable server, or pass --force.",
            file=sys.stderr,
        )
        return 1

    def records() -> Iterator[Record]:
        yield from iter_launchbox(args.metadata_zip)
        if args.titledb:
            yield from iter_titledb(args.titledb)

    benched = (DATABASE_ID_KEY, IMAGE_KEY, TITLEDB_KEY)
    results = {}
    passes = [("plain", plain), ("encoded", encode)]
    if args.only:
        passes = [p for p in passes if p[0] == args.only]

    for label, serialize in passes:
        base_used, _ = clear_stores(client)
        start = time.perf_counter()
        load(client, records(), serialize)
        elapsed = time.perf_counter() - start
        counts, value_bytes = store_stats(client)
        sizes, used, rss = measure(client, list(counts))
        # Net of anything else on the server, so a non-empty one still reports
        # what the dumps themselves cost. Only `used_memory` can be offset this
        # way; RSS keeps the pages a delete frees, so it is left absolute.
        used -= base_used
        latency = {key: bench_decode(client, key) for key in benched}
        results[label] = (counts, value_bytes, sizes, used, rss, latency)
        print(
            f"{label}: loaded in {elapsed:.0f}s, used_memory {mb(used)}, "
            f"rss {mb(rss)}"
        )

    if args.only:
        return 0

    p_counts, p_values, p_sizes, p_used, p_rss, p_latency = results["plain"]
    _, e_values, e_sizes, e_used, e_rss, e_latency = results["encoded"]

    print(f"\nCOMPRESS_MIN_BYTES = {COMPRESS_MIN_BYTES}\n")
    header = f"{'store':<40} {'fields':>10} {'plain':>9} {'encoded':>9} {'saved':>7}"
    print(header)
    print("-" * len(header))
    for key in sorted(p_sizes, key=lambda k: -p_sizes[k]):
        plain_size = p_sizes[key]
        enc_size = e_sizes.get(key, 0)
        saved = 1 - enc_size / plain_size if plain_size else 0
        print(
            f"{key:<40} {p_counts[key]:>10,} {mb(plain_size)} {mb(enc_size)} "
            f"{saved:>6.0%}"
        )
    print("-" * len(header))
    print(
        f"{'sum of stores':<40} {sum(p_counts.values()):>10,} "
        f"{mb(sum(p_sizes.values()))} {mb(sum(e_sizes.values()))} "
        f"{1 - sum(e_sizes.values()) / sum(p_sizes.values()):>6.0%}"
    )
    print(
        f"{'used_memory (dump stores)':<40} {'':>10} {mb(p_used)} {mb(e_used)} "
        f"{1 - e_used / p_used:>6.0%}"
    )
    # Absolute, and only comparable between passes on a server restarted
    # between them, which is what --only is for.
    print(f"{'used_memory_rss (absolute)':<40} {'':>10} {mb(p_rss)} {mb(e_rss)}")

    p_value_total, e_value_total = sum(p_values.values()), sum(e_values.values())
    print(
        f"\nstored value bytes: {mb(p_value_total)} -> {mb(e_value_total)} "
        f"({p_value_total / e_value_total:.2f}x)"
    )

    print(
        f"\n{'decode (us/record, mean stored bytes)':<40} {'plain':>16} {'encoded':>16}"
    )
    for key in benched:
        before, after = p_latency.get(key), e_latency.get(key)
        if not before or not after:
            continue
        print(
            f"{key:<40} {before[0]:>7.2f} {before[1]:>8,.0f} "
            f"{after[0]:>7.2f} {after[1]:>8,.0f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
