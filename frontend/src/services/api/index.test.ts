import type { InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import api from "@/services/api";

const originalAdapter = api.defaults.adapter!;

describe("network-quiesced", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["setTimeout", "clearTimeout", "Date"] });
    api.defaults.adapter = (config: InternalAxiosRequestConfig) =>
      Promise.resolve({
        data: {},
        status: 200,
        statusText: "OK",
        headers: {},
        config,
      });
  });

  afterEach(() => {
    api.defaults.adapter = originalAdapter;
    vi.unstubAllGlobals();
    vi.useRealTimers();
  });

  it("fires once the network goes quiet", async () => {
    const onQuiesced = vi.fn();
    document.addEventListener("network-quiesced", onQuiesced);

    await api.get("/ping");
    expect(onQuiesced).not.toHaveBeenCalled();

    vi.advanceTimersByTime(250);
    expect(onQuiesced).toHaveBeenCalledTimes(1);

    document.removeEventListener("network-quiesced", onQuiesced);
  });

  it("does not throw when the DOM is gone by the time it fires", async () => {
    await api.get("/ping");

    vi.stubGlobal("document", undefined);

    expect(() => vi.advanceTimersByTime(250)).not.toThrow();
  });
});
