import { describe, expect, it, vi } from "vitest";
import type { MusicTrackSchema } from "@/__generated__";
import { TRACK_PAGE_SIZE, useTrackPager } from "./index";

function track(id: number): MusicTrackSchema {
  return { rom_file_id: id } as MusicTrackSchema;
}

/** A fetcher over a synthetic catalog, recording the offsets it was asked for. */
function catalog(total: number) {
  const calls: number[] = [];
  const fetcher = async (offset: number, limit: number) => {
    calls.push(offset);
    const items = Array.from(
      { length: Math.max(0, Math.min(limit, total - offset)) },
      (_, i) => track(offset + i),
    );
    return { items, total };
  };
  return { calls, fetcher };
}

describe("useTrackPager", () => {
  it("loads only the first page on reset", async () => {
    const { calls, fetcher } = catalog(10_000);
    const pager = useTrackPager();
    await pager.reset(fetcher);

    expect(calls).toEqual([0]);
    expect(pager.tracks.value).toHaveLength(TRACK_PAGE_SIZE);
    expect(pager.total.value).toBe(10_000);
    expect(pager.hasMore.value).toBe(true);
  });

  it("appends the next page and stops at the end", async () => {
    const { calls, fetcher } = catalog(TRACK_PAGE_SIZE + 5);
    const pager = useTrackPager();
    await pager.reset(fetcher);
    await pager.loadMore();

    expect(calls).toEqual([0, TRACK_PAGE_SIZE]);
    expect(pager.tracks.value).toHaveLength(TRACK_PAGE_SIZE + 5);
    expect(pager.hasMore.value).toBe(false);

    await pager.loadMore();
    expect(calls).toHaveLength(2);
  });

  it("only fetches when the consumer is near the end of what is loaded", async () => {
    const { calls, fetcher } = catalog(10_000);
    const pager = useTrackPager();
    await pager.reset(fetcher);

    pager.loadMoreIfNear(10);
    await Promise.resolve();
    expect(calls).toEqual([0]);

    pager.loadMoreIfNear(TRACK_PAGE_SIZE - 1);
    await new Promise((r) => setTimeout(r, 0));
    expect(calls).toEqual([0, TRACK_PAGE_SIZE]);
  });

  it("does not run two page loads at once", async () => {
    const { calls, fetcher } = catalog(10_000);
    const pager = useTrackPager();
    await pager.reset(fetcher);

    await Promise.all([pager.loadMore(), pager.loadMore()]);
    expect(calls).toEqual([0, TRACK_PAGE_SIZE]);
  });

  it("drops a page that arrives after the source changed", async () => {
    let release = () => {};
    const arrived = new Promise<void>((resolve) => {
      release = resolve;
    });
    const slow = async () => {
      await arrived;
      return { items: [track(1)], total: 1 };
    };
    const pager = useTrackPager();

    const first = pager.reset(slow);
    await pager.reset(async () => ({ items: [track(99)], total: 1 }));
    release();
    await first;

    expect(pager.tracks.value.map((t) => t.rom_file_id)).toEqual([99]);
  });

  it("reports each loaded page to the observer", async () => {
    const seen = vi.fn();
    const { fetcher } = catalog(TRACK_PAGE_SIZE * 2);
    const pager = useTrackPager(seen);
    await pager.reset(fetcher);
    await pager.loadMore();

    expect(seen).toHaveBeenCalledTimes(2);
    expect(seen.mock.calls[1][0]).toHaveLength(TRACK_PAGE_SIZE);
  });

  it("leaves the list empty when the first page fails", async () => {
    const pager = useTrackPager();
    await pager.reset(async () => {
      throw new Error("boom");
    });
    expect(pager.tracks.value).toEqual([]);
    expect(pager.loading.value).toBe(false);
  });
});
