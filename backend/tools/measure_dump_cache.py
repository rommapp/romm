"""Measure what the metadata dump stores cost in a real valkey, encoded or not.

Usage:
    uv run tools/measure_dump_cache.py \
        --metadata-zip Metadata.zip --titledb US.en.json \
        --redis-url redis://localhost:6379
"""

import argparse
import json
import statistics
import sys
import time
import unicodedata
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Final

import redis
import zstandard
from defusedxml import ElementTree as ET

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handler.dump_cache import (  # noqa: E402
    COMPRESS_MIN_BYTES,
    COMPRESSION_LEVEL,
    decode,
    encode,
)

# Mirrors the two stores' keys, which live behind `handler/metadata/__init__.py`
# and its provider handlers. The only keys this tool ever deletes.
LAUNCHBOX_PLATFORMS_KEY: Final = "romm:launchbox_platforms"
LAUNCHBOX_METADATA_DATABASE_ID_KEY: Final = "romm:launchbox_metadata_database_id"
LAUNCHBOX_METADATA_NAME_KEY: Final = "romm:launchbox_metadata_name"
LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY: Final = "romm:launchbox_metadata_alternate_name"
LAUNCHBOX_METADATA_FOLDED_NAME_KEY: Final = "romm:launchbox_metadata_folded_name"
LAUNCHBOX_METADATA_IMAGE_KEY: Final = "romm:launchbox_metadata_image"
LAUNCHBOX_MAME_KEY: Final = "romm:launchbox_mame"
LAUNCHBOX_FILES_KEY: Final = "romm:launchbox_files"
SWITCH_TITLEDB_INDEX_KEY: Final = "romm:switch_titledb"
SWITCH_PRODUCT_ID_KEY: Final = "romm:switch_product_id"

DUMP_STORE_KEYS: Final[tuple[str, ...]] = (
    LAUNCHBOX_PLATFORMS_KEY,
    LAUNCHBOX_METADATA_DATABASE_ID_KEY,
    LAUNCHBOX_METADATA_NAME_KEY,
    LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
    LAUNCHBOX_METADATA_FOLDED_NAME_KEY,
    LAUNCHBOX_METADATA_IMAGE_KEY,
    LAUNCHBOX_MAME_KEY,
    LAUNCHBOX_FILES_KEY,
    SWITCH_TITLEDB_INDEX_KEY,
    SWITCH_PRODUCT_ID_KEY,
)

# Mirrors the projections in `launchbox_handler/types.py`, behind the same
# package import. Each store keeps only the fields its reader reads.
LAUNCHBOX_IMAGE_FIELDS: Final[frozenset[str]] = frozenset(
    {"FileName", "Type", "Region"}
)
LAUNCHBOX_FILE_FIELDS: Final[frozenset[str]] = frozenset({"GameName"})
LAUNCHBOX_MAME_FIELDS: Final[frozenset[str]] = frozenset({"Name"})

WRITE_BATCH = 2000

Record = tuple[str, str, Any]


def fold_title(title: str) -> str:
    """Mirror of `launchbox_handler.utils.fold_title`, behind the same package import."""
    kept: list[str] = []
    for char in unicodedata.normalize("NFKD", title.casefold()):
        if unicodedata.category(char).startswith("M"):
            if kept and "a" <= kept[-1] <= "z":
                continue
            kept.append(char)
        elif char.isalnum():
            kept.append(char)

    return "".join(kept)


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


# Mirrors the record shapes `tasks/scheduled/update_launchbox_metadata.py`
# writes, duplicated because the writer fills a pipeline rather than yielding.
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
                        yield (
                            LAUNCHBOX_PLATFORMS_KEY,
                            name.text.strip(),
                            element_to_dict(elem),
                        )

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
                            yield (
                                LAUNCHBOX_METADATA_DATABASE_ID_KEY,
                                database_id,
                                element_to_dict(elem),
                            )

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
                                LAUNCHBOX_METADATA_NAME_KEY,
                                f"{title.lower()}:{platform}",
                                database_id,
                            )
                            folded = fold_title(title)
                            if folded:
                                yield (
                                    LAUNCHBOX_METADATA_FOLDED_NAME_KEY,
                                    f"{folded}:{platform}",
                                    database_id,
                                )

                    elif elem.tag == "GameAlternateName":
                        alt = (elem.findtext("AlternateName") or "").strip()
                        alt_id = (elem.findtext("DatabaseID") or "").strip()
                        if alt and alt_id:
                            yield (
                                LAUNCHBOX_METADATA_ALTERNATE_NAME_KEY,
                                alt.lower(),
                                alt_id,
                            )

                    elif elem.tag == "GameImage":
                        id_elem = elem.find("DatabaseID")
                        if id_elem is None or not id_elem.text:
                            continue
                        current = id_elem.text.strip()
                        if image_id is not None and current != image_id:
                            yield LAUNCHBOX_METADATA_IMAGE_KEY, image_id, images
                            images = []
                        image_id = current
                        images.append(element_to_dict(elem, LAUNCHBOX_IMAGE_FIELDS))

                if image_id is not None:
                    yield LAUNCHBOX_METADATA_IMAGE_KEY, image_id, images

        if "Mame.xml" in names:
            with z.open("Mame.xml") as f:
                for elem in iter_elements(f):
                    if elem.tag != "MameFile":
                        continue
                    fn = elem.find("FileName")
                    if fn is not None and fn.text:
                        yield (
                            LAUNCHBOX_MAME_KEY,
                            fn.text.strip(),
                            element_to_dict(elem, LAUNCHBOX_MAME_FIELDS),
                        )

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
                        yield (
                            LAUNCHBOX_FILES_KEY,
                            field,
                            element_to_dict(elem, LAUNCHBOX_FILE_FIELDS),
                        )


def iter_titledb(titledb: Path) -> Iterator[Record]:
    data = json.loads(titledb.read_text())
    relevant = {k: v for k, v in data.items() if k and v}
    del data
    for title_id, entry in relevant.items():
        yield SWITCH_TITLEDB_INDEX_KEY, title_id, entry
    for title_id, entry in relevant.items():
        product_id = entry.get("id")
        if product_id:
            yield SWITCH_PRODUCT_ID_KEY, product_id, title_id


def plain(value: Any) -> bytes:
    """Serialize a record as the uncompressed baseline the report compares to."""
    return json.dumps(value).encode()


def compact(value: Any) -> bytes:
    """Serialize a record the way `encode` does before it decides to compress."""
    return json.dumps(value, separators=(",", ":")).encode()


def load(
    client: redis.Redis, records: Iterator[Record], serialize: Callable[[Any], bytes]
) -> None:
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
    """Field count and total value bytes per store, read back off the hashes."""
    # Not tallied while writing: the dump repeats a title on one platform and an
    # alternate name across platforms, so ~9k records overwrite another's field.
    counts: dict[str, int] = {}
    value_bytes: dict[str, int] = {}
    for key in DUMP_STORE_KEYS:
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
    owned = {key.encode() for key in DUMP_STORE_KEYS}
    return sum(1 for key in client.scan_iter(count=1000) if key not in owned)


def clear_stores(client: redis.Redis) -> int:
    """Drop only this tool's stores, returning `used_memory` without them."""
    # Not `flushall`: the URL can point at a live RomM, whose sessions and RQ
    # queues share the database with these stores.
    client.delete(*DUMP_STORE_KEYS)
    return int(client.info("memory")["used_memory"])


def store_memory(
    client: redis.Redis, keys: list[str]
) -> tuple[dict[str, int], int, int]:
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


def sweep_threshold(metadata_zip: Path, limit: int) -> int:
    """Print total stored bytes at each candidate COMPRESS_MIN_BYTES, on real
    records, and return an exit code."""
    compressor = zstandard.ZstdCompressor(level=COMPRESSION_LEVEL)
    sample: list[bytes] = []
    for _, _, value in iter_launchbox(metadata_zip):
        # The threshold is compared against the payload `encode` builds, not
        # the wider baseline the report uses for the old format.
        sample.append(compact(value))
        if len(sample) >= limit:
            break

    if not sample:
        print("no records in the zip; check --metadata-zip", file=sys.stderr)
        return 1

    raw = sum(len(payload) for payload in sample)
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
        label = "never" if threshold == 1 << 30 else f"{threshold}"
        print(
            f"{label:>10} {mb(total)} {raw / total:>6.2f}x "
            f"{compressed / len(sample):>10.0%}"
        )

    return 0


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
        return sweep_threshold(args.metadata_zip, args.sweep)

    client = redis.Redis.from_url(args.redis_url)

    foreign = foreign_keys(client)
    if foreign and not args.force:
        # The URL is not echoed back: RomM builds it with the password inline.
        print(
            f"The target server holds {foreign:,} key(s) outside the metadata "
            "dump stores, so it looks like a live instance. This tool drops and "
            "rebuilds the dump stores, which a running RomM would then have to "
            "re-import. Point it at a disposable server, or pass --force.",
            file=sys.stderr,
        )
        return 1

    def records() -> Iterator[Record]:
        yield from iter_launchbox(args.metadata_zip)
        if args.titledb:
            yield from iter_titledb(args.titledb)

    benched = (
        LAUNCHBOX_METADATA_DATABASE_ID_KEY,
        LAUNCHBOX_METADATA_IMAGE_KEY,
        SWITCH_TITLEDB_INDEX_KEY,
    )
    results = {}
    passes = [("plain", plain), ("encoded", encode)]
    if args.only:
        passes = [p for p in passes if p[0] == args.only]

    for label, serialize in passes:
        base_used = clear_stores(client)
        start = time.perf_counter()
        load(client, records(), serialize)
        elapsed = time.perf_counter() - start
        counts, value_bytes = store_stats(client)
        sizes, used, rss = store_memory(client, list(counts))
        # Net of anything else on the server. Only `used_memory` can be offset
        # this way; RSS keeps the pages a delete frees, so it stays absolute.
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

    if not p_sizes:
        print("no records loaded; check --metadata-zip", file=sys.stderr)
        return 1

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
    # Only comparable between passes on a server restarted between them,
    # which is what --only is for.
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
