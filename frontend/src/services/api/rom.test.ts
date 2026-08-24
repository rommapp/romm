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

function startBody(): Record<string, unknown> {
  const start = post.mock.calls.find(([url]) => url === "/roms/upload/start");
  return start?.[1] ?? {};
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
    expect(startBody()).toEqual({
      platform_id: 3,
      filename: "fix.ips",
      total_size: 3,
      total_chunks: 1,
      rom_id: 42,
      folder: "hack/v2",
    });
    expect(post).toHaveBeenCalledWith(
      "/roms/upload/u-1/complete",
      null,
      expect.anything(),
    );
  });

  it("leaves the rom fields out of a platform upload", async () => {
    await romApi.uploadRoms({
      platformId: 3,
      filesToUpload: [new File(["abc"], "game.zip")],
    });

    expect(startBody()).toEqual({
      platform_id: 3,
      filename: "game.zip",
      total_size: 3,
      total_chunks: 1,
    });
  });

  it("treats an empty folder as the rom root", async () => {
    await romApi.uploadRoms({
      platformId: 3,
      romId: 42,
      folder: "",
      filesToUpload: [new File(["abc"], "readme.txt")],
    });

    expect(startBody()).toMatchObject({ rom_id: 42 });
    expect(startBody()).not.toHaveProperty("folder");
  });
});
