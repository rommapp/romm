import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import romApi, { type UpdateRom } from "@/services/api/rom";

const { post, put } = vi.hoisted(() => ({
  post: vi.fn(),
  put: vi.fn(),
}));

vi.mock("@/services/api", () => ({
  default: { post, put, get: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/services/socket", () => ({
  default: { emit: vi.fn(), connected: true, connect: vi.fn() },
}));

/** The FormData `updateRom` put on the wire. */
async function sentFields(rom: UpdateRom): Promise<FormData> {
  await romApi.updateRom({ rom });
  return put.mock.calls[0][1] as FormData;
}

function buildRom(overrides: Partial<UpdateRom> = {}): UpdateRom {
  return { id: 1, name: "Game", ...overrides } as UpdateRom;
}

function startCall(): { body: unknown; headers: Record<string, string> } {
  const start = post.mock.calls.find(([url]) => url === "/roms/upload/start");
  return { body: start?.[1], headers: start?.[2]?.headers ?? {} };
}

describe("updateRom", () => {
  beforeEach(() => {
    put.mockReset();
    put.mockResolvedValue({ data: {} });
  });

  // An id missing from the serializer is silently dropped: the endpoint
  // preserves the stored value for any field the form omits, so the save
  // reports success while the edit never lands.
  it.each([
    "igdb_id",
    "sgdb_id",
    "moby_id",
    "ss_id",
    "launchbox_id",
    "ra_id",
    "flashpoint_id",
    "hasheous_id",
    "tgdb_id",
    "hltb_id",
    "steam_id",
    "libretro_id",
  ])("sends %s", async (field) => {
    const fields = await sentFields(buildRom({ [field]: 1234 }));

    expect(fields.get(field)).toBe("1234");
  });

  it.each([
    "igdb_metadata",
    "moby_metadata",
    "ss_metadata",
    "launchbox_metadata",
    "hasheous_metadata",
    "flashpoint_metadata",
    "hltb_metadata",
    "steam_metadata",
  ])("sends edited raw %s", async (field) => {
    const raw = JSON.stringify({ edited: true });

    const fields = await sentFields(
      buildRom({ raw_metadata: { [field]: raw } }),
    );

    expect(fields.get(`raw_${field}`)).toBe(raw);
  });
});

describe("romApi.uploadRoms", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    post.mockReset();
    put.mockReset();
    post.mockResolvedValue({ data: { upload_id: "u-1" } });
    put.mockResolvedValue({ data: { received: 1, total: 1 } });
  });

  it("targets a rom folder through the start payload", async () => {
    const results = await romApi.uploadRoms({
      platformId: 3,
      romId: 42,
      folder: "hack/v2",
      filesToUpload: [new File(["abc"], "fix.ips")],
    });

    expect(results[0].status).toBe("fulfilled");
    expect(startCall().headers).toMatchObject({
      "X-Upload-Platform": "3",
      "X-Upload-Filename": "fix.ips",
    });
    expect(startCall().body).toEqual({ rom_id: 42, folder: "hack/v2" });
    expect(post).toHaveBeenCalledWith(
      "/roms/upload/u-1/complete",
      null,
      expect.anything(),
    );
  });

  it("sends no body for a platform upload", async () => {
    await romApi.uploadRoms({
      platformId: 3,
      filesToUpload: [new File(["abc"], "game.zip")],
    });

    expect(startCall().body).toBeNull();
    expect(startCall().headers["X-Upload-Filename"]).toBe("game.zip");
  });

  it("treats an empty folder as the rom root", async () => {
    await romApi.uploadRoms({
      platformId: 3,
      romId: 42,
      folder: "",
      filesToUpload: [new File(["abc"], "readme.txt")],
    });

    expect(startCall().body).toEqual({ rom_id: 42 });
  });
});
