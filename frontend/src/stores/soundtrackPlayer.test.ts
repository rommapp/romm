import { describe, expect, it } from "vitest";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import {
  resolveSoundtrackGameArtwork,
  type SoundtrackArtworkRom,
} from "./soundtrackPlayer";

function makeRom(
  overrides: Partial<SoundtrackArtworkRom> = {},
): SoundtrackArtworkRom {
  return {
    ss_metadata: null,
    launchbox_metadata: null,
    platform_slug: "psx",
    path_cover_large: null,
    path_cover_small: null,
    url_cover: null,
    ...overrides,
  } as SoundtrackArtworkRom;
}

describe("resolveSoundtrackGameArtwork", () => {
  it("prefers the ScreenScraper disc over the logo on a CD system", () => {
    const url = resolveSoundtrackGameArtwork(
      makeRom({
        ss_metadata: { physical_path: "disc.png", logo_path: "logo.png" },
      }),
    );
    expect(url).toBe(`${FRONTEND_RESOURCES_PATH}/disc.png`);
  });

  it("falls back to the LaunchBox disc when ScreenScraper has none", () => {
    const url = resolveSoundtrackGameArtwork(
      makeRom({
        ss_metadata: { logo_path: "logo.png" },
        launchbox_metadata: {
          images: [
            {
              url: "https://images.launchbox-app.com/box.png",
              type: "Box - Front",
            },
            { url: "https://images.launchbox-app.com/disc.png", type: "Disc" },
          ],
        },
      }),
    );
    expect(url).toBe("https://images.launchbox-app.com/disc.png");
  });

  it("skips LaunchBox media the browser cannot load", () => {
    const url = resolveSoundtrackGameArtwork(
      makeRom({
        ss_metadata: { logo_path: "logo.png" },
        launchbox_metadata: {
          images: [
            { url: "launchbox-file://Images/PS1/Disc/game.png", type: "Disc" },
          ],
        },
      }),
    );
    expect(url).toBe(`${FRONTEND_RESOURCES_PATH}/logo.png`);
  });

  it("ignores physical media on a non-CD system", () => {
    const url = resolveSoundtrackGameArtwork(
      makeRom({
        platform_slug: "snes",
        ss_metadata: { physical_path: "cart.png", logo_path: "logo.png" },
        launchbox_metadata: {
          images: [
            { url: "https://images.launchbox-app.com/disc.png", type: "Disc" },
          ],
        },
      }),
    );
    expect(url).toBe(`${FRONTEND_RESOURCES_PATH}/logo.png`);
  });

  it("falls back to the cover chain when no artwork is scraped", () => {
    expect(
      resolveSoundtrackGameArtwork(
        makeRom({ path_cover_small: "small.png", url_cover: "remote.png" }),
      ),
    ).toBe("small.png");
    expect(resolveSoundtrackGameArtwork(makeRom())).toBeUndefined();
  });
});
