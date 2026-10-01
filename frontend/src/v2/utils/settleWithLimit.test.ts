import { describe, expect, it } from "vitest";
import { settleWithLimit } from "./settleWithLimit";

describe("settleWithLimit", () => {
  it("never runs more than the limit at once", async () => {
    let inFlight = 0;
    let peak = 0;
    const task = async (n: number) => {
      inFlight++;
      peak = Math.max(peak, inFlight);
      await new Promise((resolve) => setTimeout(resolve, 0));
      inFlight--;
      return n * 2;
    };

    const results = await settleWithLimit([1, 2, 3, 4, 5, 6, 7], 3, task);

    expect(peak).toBe(3);
    expect(results).toEqual(
      [2, 4, 6, 8, 10, 12, 14].map((value) => ({
        status: "fulfilled",
        value,
      })),
    );
  });

  it("keeps each rejection at its item's index", async () => {
    const results = await settleWithLimit([1, 2, 3], 2, async (n) => {
      if (n === 2) throw new Error("boom");
      return n;
    });

    expect(results.map((r) => r.status)).toEqual([
      "fulfilled",
      "rejected",
      "fulfilled",
    ]);
  });

  it("resolves an empty list", async () => {
    expect(await settleWithLimit([], 4, async () => 1)).toEqual([]);
  });
});
