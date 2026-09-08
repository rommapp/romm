import { createPinia, setActivePinia } from "pinia";
import { describe, expect, it, vi } from "vitest";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import useSoundtrackPlayer, {
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

describe("loadPlaylist with preserved shuffle", () => {
  function makeTracks(count: number, offset = 0) {
    return Array.from({ length: count }, (_, i) => ({
      romId: 1,
      fileId: offset + i + 1,
      fileName: `track-${offset + i + 1}.mp3`,
      url: `/tracks/${offset + i + 1}`,
    }));
  }

  it("shuffles freshly paged-in tracks instead of appending them in order", () => {
    setActivePinia(createPinia());
    const player = useSoundtrackPlayer();
    const firstPage = makeTracks(4);
    player.loadPlaylist(firstPage, {}, null);
    player.toggleShuffle();
    const shuffledFirstPage = [...player.playlist];

    const nextPage = makeTracks(4, 4);
    // Force the worst shuffle luck: Math.random() = 0 still may not produce
    // the identity permutation, so an in-order tail proves the bug.
    const randomSpy = vi.spyOn(Math, "random").mockReturnValue(0);
    player.loadPlaylist([...firstPage, ...nextPage], {}, null, true);
    randomSpy.mockRestore();

    const ids = (tracks: { fileId: number }[]) => tracks.map((t) => t.fileId);
    // The already-shuffled window keeps its order.
    expect(ids(player.playlist.slice(0, 4))).toEqual(ids(shuffledFirstPage));
    // The appended window holds the same tracks but not in server order.
    expect(ids(player.playlist.slice(4)).sort()).toEqual(ids(nextPage).sort());
    expect(ids(player.playlist.slice(4))).not.toEqual(ids(nextPage));
  });
});
