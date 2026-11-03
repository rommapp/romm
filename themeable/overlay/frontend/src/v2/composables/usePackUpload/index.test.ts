import { AxiosError, AxiosHeaders } from "axios";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope } from "vue";

const uploadPack = vi.fn();
vi.mock("@/services/api/themeable", () => ({ default: { uploadPack } }));
vi.mock("vue-i18n");

const { usePackUpload } = await import("./index");

const MAX = 2 * 1024 * 1024;
const STATUS = { ok: true, packs: [] };

function refused(status: number, detail: unknown) {
  return new AxiosError("refused", String(status), undefined, undefined, {
    status,
    statusText: "",
    headers: {},
    config: { headers: new AxiosHeaders() },
    data: { detail },
  });
}

function file(name: string, size = 10) {
  return new File([new Uint8Array(size)], name);
}

function setup(confirmed = true) {
  const confirmReplace = vi.fn(() => Promise.resolve(confirmed));
  const scope = effectScope();
  const upload = scope.run(() => usePackUpload(MAX, confirmReplace))!;
  return { ...upload, confirmReplace };
}

describe("usePackUpload", () => {
  beforeEach(() => uploadPack.mockReset());

  it("refuses anything but a .zip, and files over the limit, without sending", async () => {
    const { upload, error } = setup();
    expect(await upload(file("pack.tar"))).toBeNull();
    expect(error.value).toBe("branding.upload-not-zip");
    expect(await upload(file("pack.zip", MAX + 1))).toBeNull();
    expect(error.value).toMatch(/^branding.upload-too-large:.*"mb":2/);
    expect(uploadPack).not.toHaveBeenCalled();
  });

  it("returns the new status for an accepted pack", async () => {
    uploadPack.mockResolvedValue({ data: STATUS });
    const { upload, error, uploading } = setup();
    const pending = upload(file("Pack.ZIP"));
    expect(uploading.value).toBe(true);
    expect(await pending).toBe(STATUS);
    expect(uploading.value).toBe(false);
    expect(error.value).toBeNull();
  });

  it("treats a status that isn't ok as a refusal with its reason", async () => {
    uploadPack.mockResolvedValue({
      data: { ok: false, error: "dusk was installed meanwhile", packs: [] },
    });
    const { upload, error } = setup();
    expect(await upload(file("dusk.zip"))).toBeNull();
    expect(error.value).toBe("dusk was installed meanwhile");
  });

  it("asks before replacing an installed pack and resends only when confirmed", async () => {
    const clash = { message: "installed", id: "dusk", name: "Dusk" };
    uploadPack
      .mockRejectedValueOnce(refused(409, clash))
      .mockResolvedValueOnce({ data: STATUS });
    const yes = setup(true);
    expect(await yes.upload(file("dusk.zip"))).toBe(STATUS);
    expect(yes.confirmReplace).toHaveBeenCalledWith(clash);
    expect(uploadPack).toHaveBeenLastCalledWith(expect.any(File), true);

    uploadPack.mockReset().mockRejectedValueOnce(refused(409, clash));
    const no = setup(false);
    expect(await no.upload(file("dusk.zip"))).toBeNull();
    expect(uploadPack).toHaveBeenCalledOnce();
  });

  it("keeps the server's problems when it refuses a pack", async () => {
    uploadPack.mockRejectedValueOnce(
      refused(422, {
        message: "The pack can't be installed",
        problems: ["a", "b"],
      }),
    );
    const { upload, error, problems } = setup();
    expect(await upload(file("bad.zip"))).toBeNull();
    expect(error.value).toBe("The pack can't be installed");
    expect(problems.value).toEqual(["a", "b"]);

    uploadPack.mockRejectedValueOnce(refused(413, "too large"));
    expect(await upload(file("big.zip"))).toBeNull();
    expect(problems.value).toEqual([]);
    expect(error.value).toMatch(/^branding.upload-too-large/);
  });
});
