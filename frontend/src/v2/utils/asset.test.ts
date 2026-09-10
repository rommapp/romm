import { describe, expect, it } from "vitest";
import type { SaveSchema, StateSchema } from "@/__generated__";
import { type Asset, assetScreenshotUrl } from "./asset";

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

  // Saves and states resolve the same way; a `type`-aware caller would hide a
  // save's own capture, which is the bug #4422 tracks elsewhere.
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
