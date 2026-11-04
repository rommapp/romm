import { beforeEach, describe, expect, it } from "vitest";
import {
  createRetryBackoff,
  RETRY_BACKOFF_MAX_MS,
  RETRY_BACKOFF_MIN_MS,
} from "./retryBackoff";

describe("createRetryBackoff", () => {
  let clock = 0;
  const backoff = () => createRetryBackoff(() => clock);

  beforeEach(() => {
    clock = 0;
  });

  it("tries straight away until something has failed", () => {
    expect(backoff().ready()).toBe(true);
  });

  // Once a second only hammers a server that keeps saying no.
  it("doubles the wait after each failure, up to a cap", () => {
    const retry = backoff();
    const waits: number[] = [];
    for (let i = 0; i < 6; i++) {
      retry.failed();
      const start = clock;
      while (!retry.ready()) clock += 1_000;
      waits.push(clock - start);
    }

    expect(waits).toEqual([
      RETRY_BACKOFF_MIN_MS,
      4_000,
      8_000,
      16_000,
      RETRY_BACKOFF_MAX_MS,
      RETRY_BACKOFF_MAX_MS,
    ]);
  });

  it("starts over once an upload lands or the server is back", () => {
    const retry = backoff();
    retry.failed();
    retry.failed();
    expect(retry.ready()).toBe(false);

    retry.reset();
    expect(retry.ready()).toBe(true);

    retry.failed();
    clock += RETRY_BACKOFF_MIN_MS;
    expect(retry.ready()).toBe(true);
  });
});
