import { AxiosError, AxiosHeaders } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { browserDeviceId } from "./browserDevice";

const mocks = vi.hoisted(() => ({ registerDevice: vi.fn() }));

vi.mock("@/services/api/sync", () => ({
  default: { registerDevice: mocks.registerDevice },
}));

beforeEach(() => {
  localStorage.clear();
  mocks.registerDevice.mockReset();
  mocks.registerDevice.mockResolvedValue({ data: { device_id: "device-1" } });
});

describe("browserDeviceId", () => {
  it("registers this browser once per account, by its own id", async () => {
    expect(await browserDeviceId(1)).toBe("device-1");
    expect(await browserDeviceId(1)).toBe("device-1");
    await browserDeviceId(2);

    expect(mocks.registerDevice).toHaveBeenCalledTimes(2);
    const [first, second] = mocks.registerDevice.mock.calls.map(
      ([payload]) => payload,
    );
    expect(first).toMatchObject({
      platform: "Web",
      sync_mode: "api",
      allow_existing: true,
    });
    expect(first.hostname).toBeTruthy();
    expect(second.hostname).toBe(first.hostname);
  });

  it("registers again on refresh", async () => {
    await browserDeviceId(1);
    mocks.registerDevice.mockResolvedValue({ data: { device_id: "device-2" } });

    expect(await browserDeviceId(1, { refresh: true })).toBe("device-2");
    expect(await browserDeviceId(1)).toBe("device-2");
  });

  it("gives no device to an account that cannot register one", async () => {
    mocks.registerDevice.mockRejectedValue(
      new AxiosError("forbidden", "ERR", undefined, undefined, {
        status: 403,
        statusText: "",
        data: null,
        headers: {},
        config: { headers: new AxiosHeaders() },
      }),
    );

    expect(await browserDeviceId(1)).toBeNull();
  });
});
