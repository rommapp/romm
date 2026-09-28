import { describe, expect, it } from "vitest";
import type { MusicTrackSchema, TrackMetaSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import { makeDetailedRom } from "@/utils/rom.fixtures";
import {
  isAudioFile,
  isChiptuneFile,
  nowPlayingCaption,
  panelTracksFromCatalog,
  panelTracksFromRom,
  playerCoverUrl,
  romFolderCoverUrl,
} from "./soundtrackTracks";

function romFile(id: number, fileName: string, category = "soundtrack") {
  return { id, file_name: fileName, category, file_size_bytes: 1024 };
}

function rom(files: unknown[]): DetailedRom {
  return makeDetailedRom({ id: 7, files: files as DetailedRom["files"] });
}

describe("isAudioFile", () => {
  it("recognises the playable extensions only", () => {
    expect(isAudioFile("01 - Theme.mp3")).toBe(true);
    expect(isAudioFile("track.FLAC")).toBe(true);
    expect(isAudioFile("cover.png")).toBe(false);
    expect(isAudioFile("noextension")).toBe(false);
  });

  it("counts chiptune files as playable", () => {
    expect(isAudioFile("Mega Man 2.nsf")).toBe(true);
    expect(isChiptuneFile("Stage 1.SPC")).toBe(true);
    expect(isChiptuneFile("01 - Theme.mp3")).toBe(false);
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
    const meta = new Map<number, TrackMetaSchema[]>([
      [
        1,
        [
          {
            title: "Green Hill",
            artist: "Nakamura",
            album: "Sonic OST",
          } as TrackMetaSchema,
        ],
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

  it("lists each song of a chiptune file, with its sidecar playlist", () => {
    const songs = [
      { song: 0, title: "Intro", m3u_file_id: 2 },
      { song: 1, title: null, track: 2, m3u_file_id: 2 },
    ] as TrackMetaSchema[];
    const tracks = panelTracksFromRom(
      rom([romFile(1, "Game.nsf"), romFile(2, "Game.m3u")]),
      new Map([[1, songs]]),
    );
    expect(tracks.map((t) => [t.key, t.song, t.title])).toEqual([
      ["1", 0, "Intro"],
      ["1:1", 1, "Game #2"],
    ]);
    expect(tracks[1].m3uUrl).toContain("Game.m3u");
  });
});

describe("panelTracksFromCatalog", () => {
  const base = {
    rom_file_id: 5,
    rom_id: 9,
    file_name: "overworld.mp3",
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

  it("titles an untagged track by its file name, keeping the game as context", () => {
    const [track] = panelTracksFromCatalog([
      {
        ...base,
        file_name: "Stage 1.spc",
        title: null,
        artist: null,
        album: null,
      },
    ]);
    expect(track.title).toBe("Stage 1");
    expect(track.fileName).toBe("Stage 1.spc");
    expect(track.subtitle).toBe("Super Mario Bros · NES");
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

describe("nowPlayingCaption", () => {
  it("prefers the album and falls back to the artist", () => {
    expect(nowPlayingCaption({ album: "OST", artist: "Composer" })).toBe("OST");
    expect(nowPlayingCaption({ album: null, artist: "Composer" })).toBe(
      "Composer",
    );
    expect(nowPlayingCaption({})).toBe("");
    expect(nowPlayingCaption(undefined)).toBe("");
  });
});

describe("playerCoverUrl", () => {
  it("walks from the track's art to the ROM's, then the default", () => {
    expect(
      playerCoverUrl({ coverUrl: "/track.jpg", gameArtworkUrl: "/game.jpg" }),
    ).toBe("/track.jpg");
    expect(
      playerCoverUrl({
        folderCoverUrl: "/folder.jpg",
        gameArtworkUrl: "/game.jpg",
      }),
    ).toBe("/folder.jpg");
    expect(playerCoverUrl({ gameArtworkUrl: "/game.jpg" })).toBe("/game.jpg");
    expect(playerCoverUrl({})).toBe("/assets/default/album_cover.jpg");
  });

  it("skips empty URLs instead of rendering a broken image", () => {
    expect(
      playerCoverUrl({ coverUrl: "", folderCoverUrl: "", gameArtworkUrl: "" }),
    ).toBe("/assets/default/album_cover.jpg");
    expect(playerCoverUrl({ coverUrl: "", gameArtworkUrl: "/game.jpg" })).toBe(
      "/game.jpg",
    );
  });
});
