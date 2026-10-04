import { beforeEach, describe, expect, it, vi } from "vitest";
import saveApi, { UNLOAD_SAVE_MAX_BYTES } from "@/services/api/save";
import { saveFixture } from "@/utils/assets.fixtures";
import { detailedRomFixture } from "@/utils/rom.fixtures";

vi.mock("@/services/api", () => ({
  default: {
    getUri: ({
      url,
      params,
    }: {
      url: string;
      params?: Record<string, unknown>;
    }) => {
      const query = new URLSearchParams();
      for (const [key, value] of Object.entries(params ?? {})) {
        if (value !== undefined && value !== null) {
          query.append(key, String(value));
        }
      }
      const search = query.toString();
      return `/api${url}${search ? `?${search}` : ""}`;
    },
  },
}));

const rom = detailedRomFixture({ id: 1 });
const saveOf = (size: number) => new File([new Uint8Array(size)], "game.srm");

describe("sendSaveOnUnload", () => {
  const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(new Response());

  beforeEach(() => {
    vi.stubGlobal("fetch", fetchMock);
    document.cookie = "romm_csrftoken=token";
  });

  it("opens a version with a keepalive request the page does not wait for", () => {
    const sent = saveApi.sendSaveOnUnload({
      rom,
      save: null,
      saveFile: saveOf(16),
      emulator: "snes9x",
      deviceId: "dev",
      slot: "autosave",
      autocleanup: true,
    });

    expect(sent).toBe(true);
    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe(
      "/api/saves?rom_id=1&emulator=snes9x&device_id=dev&slot=autosave&autocleanup=true&overwrite=true",
    );
    expect(init).toMatchObject({
      method: "POST",
      keepalive: true,
      credentials: "same-origin",
      headers: { "x-csrftoken": "token" },
    });
    expect((init?.body as FormData).get("saveFile")).toBeInstanceOf(File);
  });

  it("keeps the stale-device guard when the caller asks for it", () => {
    saveApi.sendSaveOnUnload({
      rom,
      save: null,
      saveFile: saveOf(16),
      deviceId: "dev",
      slot: "Save01",
      overwrite: false,
    });

    const [url] = fetchMock.mock.calls[0]!;
    expect(url).toBe(
      "/api/saves?rom_id=1&device_id=dev&slot=Save01&overwrite=false",
    );
  });

  it("updates the session's version in place", () => {
    saveApi.sendSaveOnUnload({
      rom,
      save: saveFixture({ id: 3 }),
      saveFile: saveOf(16),
      deviceId: "dev",
    });

    const [url, init] = fetchMock.mock.calls[0]!;
    expect(url).toBe("/api/saves/3?device_id=dev");
    expect(init).toMatchObject({ method: "PUT", keepalive: true });
  });

  it("refuses a save a keepalive body cannot carry", () => {
    const sent = saveApi.sendSaveOnUnload({
      rom,
      save: null,
      saveFile: saveOf(UNLOAD_SAVE_MAX_BYTES + 1),
    });

    expect(sent).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
