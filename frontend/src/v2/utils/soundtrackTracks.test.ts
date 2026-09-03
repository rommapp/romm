import { describe, expect, it } from "vitest";
import type { MusicTrackSchema, TrackMetaSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import {
  isAudioFile,
  panelTracksFromCatalog,
  panelTracksFromRom,
  romFolderCoverUrl,
} from "./soundtrackTracks";

function romFile(id: number, fileName: string, category = "soundtrack") {
  return { id, file_name: fileName, category, file_size_bytes: 1024 };
}

function rom(files: unknown[]): DetailedRom {
  return { id: 7, files } as unknown as DetailedRom;
}

describe("isAudioFile", () => {
  it("recognises the playable extensions only", () => {
    expect(isAudioFile("01 - Theme.mp3")).toBe(true);
    expect(isAudioFile("track.FLAC")).toBe(true);
    expect(isAudioFile("cover.png")).toBe(false);
    expect(isAudioFile("noextension")).toBe(false);
  });
});

describe("panelTracksFromRom", () => {
  it("keeps only audio soundtrack files, sorted by file name", () => {
    const tracks = panelTracksFromRom(
      rom([
        romFile(2, "02 - Battle.mp3"),
        romFile(1, "01 - Theme.mp3"),
        romFile(3, "cover.png"),
        romFile(4, "manual.pdf", "manual"),
      ]),
      new Map(),
    );
    expect(tracks.map((t) => t.fileName)).toEqual([
      "01 - Theme.mp3",
      "02 - Battle.mp3",
    ]);
  });

  it("prefers metadata for the title and builds an artist/album subtitle", () => {
    const meta = new Map<number, TrackMetaSchema>([
      [
        1,
        {
          title: "Green Hill",
          artist: "Nakamura",
          album: "Sonic OST",
        } as TrackMetaSchema,
      ],
    ]);
    const [track] = panelTracksFromRom(
      rom([romFile(1, "01 - track.mp3")]),
      meta,
    );
    expect(track.title).toBe("Green Hill");
    expect(track.subtitle).toBe("Nakamura · Sonic OST");
  });

  it("falls back to the file name without its extension", () => {
    const [track] = panelTracksFromRom(
      rom([romFile(1, "01 - Theme.mp3")]),
      new Map(),
    );
    expect(track.title).toBe("01 - Theme");
    expect(track.subtitle).toBe("");
  });
});

describe("panelTracksFromCatalog", () => {
  const base = {
    rom_file_id: 5,
    rom_id: 9,
    title: "Overworld",
    artist: "Kondo",
    album: "SMB OST",
    game_name: "Super Mario Bros",
    platform_name: "NES",
    stream_url: "/api/roms/5/files/content/overworld.mp3",
    duration_seconds: 90,
  } as MusicTrackSchema;

  it("adds the game and platform as context", () => {
    const [track] = panelTracksFromCatalog([base]);
    expect(track.subtitle).toBe("Kondo · SMB OST · Super Mario Bros · NES");
    expect(track.durationSeconds).toBe(90);
  });

  it("drops the game name when it merely repeats the title", () => {
    const [track] = panelTracksFromCatalog([
      { ...base, title: "Super Mario Bros", artist: null, album: null },
    ]);
    expect(track.subtitle).toBe("NES");
  });
});

describe("romFolderCoverUrl", () => {
  it("picks the first cover image beside the tracks", () => {
    const url = romFolderCoverUrl(
      rom([romFile(3, "z.png"), romFile(2, "a.jpg"), romFile(1, "song.mp3")]),
    );
    expect(url).toContain("a.jpg");
  });

  it("is undefined when the folder has no image", () => {
    expect(romFolderCoverUrl(rom([romFile(1, "song.mp3")]))).toBeUndefined();
  });
});
