import { describe, expect, it } from "vitest";
import type { SaveSchema, StateSchema } from "@/__generated__";
import type { UserSaveSchema } from "@/__generated__";
import { type Asset, assetOwner, assetScreenshotUrl } from "./asset";

function makeAsset(screenshot: Asset["screenshot"]): Asset {
  return { id: 1, file_name: "slot_1.srm", screenshot } as SaveSchema;
}

describe("assetScreenshotUrl", () => {
  it("returns the capture's download path", () => {
    const asset = makeAsset({
      id: 3,
      download_path: "/api/screenshots/3/content",
    } as StateSchema["screenshot"]);

    expect(assetScreenshotUrl(asset)).toBe("/api/screenshots/3/content");
  });

  it("returns null when the asset has no capture", () => {
    expect(assetScreenshotUrl(makeAsset(null))).toBeNull();
  });

  // A type-aware caller would hide a save's own capture.
  it("does not discriminate between saves and states", () => {
    const shot = {
      id: 4,
      download_path: "/api/screenshots/4/content",
    } as StateSchema["screenshot"];

    expect(assetScreenshotUrl({ ...makeAsset(shot) } as SaveSchema)).toBe(
      assetScreenshotUrl({ ...makeAsset(shot) } as unknown as StateSchema),
    );
  });
});

describe("assetOwner", () => {
  it("returns the author of a community asset", () => {
    const asset = { id: 1, username: "ada" } as UserSaveSchema;

    expect(assetOwner(asset)?.username).toBe("ada");
  });

  // Own assets come back without a username, and the backend can send an
  // empty one; neither should render an author chip.
  it("returns null when there is no author to credit", () => {
    expect(assetOwner({ id: 1 } as Asset)).toBeNull();
    expect(assetOwner({ id: 1, username: "" } as UserSaveSchema)).toBeNull();
  });
});
