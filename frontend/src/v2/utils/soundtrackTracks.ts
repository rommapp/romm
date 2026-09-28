// The one track shape the soundtrack player renders; both sources (a ROM's
// own files, the music catalog) normalize into it here.
import type { MusicTrackSchema, TrackMetaSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import { playerTrackKey, type PlayerMeta } from "@/stores/soundtrackPlayer";
import { FRONTEND_RESOURCES_PATH } from "@/utils";
import { romFileUrl } from "@/v2/utils/romFiles";

export interface PanelTrack {
  /** `rom_file_id`, shared by the songs of one file. */
  id: number;
  /** The song within the file; 0 unless the file holds several. */
  song: number;
  /** Identifies the track within its ROM, song included. */
  key: string;
  romId: number;
  fileName: string;
  /** Display title, already resolved from metadata or the file name. */
  title: string;
  /** Artist · album · (game · platform), whatever the source could supply. */
  subtitle: string;
  url: string;
  /** The sidecar playlist a chiptune file is played with. */
  m3uUrl?: string;
  durationSeconds?: number;
  fileSizeBytes?: number;
  coverUrl?: string;
  gameArtworkUrl?: string;
  meta?: TrackMetaSchema;
}

const AUDIO_EXTS = new Set(["mp3", "ogg", "oga", "wav", "flac", "m4a", "opus"]);
// Console sound formats, played through game-music-emu instead of `<audio>`.
const CHIPTUNE_EXTS = new Set([
  "ay",
  "gbs",
  "gym",
  "hes",
  "kss",
  "nsf",
  "nsfe",
  "sap",
  "spc",
  "vgm",
  "vgz",
]);
const COVER_EXTS = new Set(["jpg", "jpeg", "png", "webp", "gif"]);

/** The file picker filter for soundtrack uploads. */
export const SOUNDTRACK_ACCEPT = [
  "audio/*",
  ".flac",
  ".opus",
  ...[...CHIPTUNE_EXTS].map((ext) => `.${ext}`),
  // The playlist that names and orders a chiptune file's songs.
  ".m3u",
].join(",");

export function getExt(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot + 1).toLowerCase();
}

export function isAudioFile(name: string): boolean {
  const ext = getExt(name);
  return AUDIO_EXTS.has(ext) || CHIPTUNE_EXTS.has(ext);
}

export function isChiptuneFile(name: string): boolean {
  return CHIPTUNE_EXTS.has(getExt(name));
}

export function isCoverFile(name: string): boolean {
  return COVER_EXTS.has(getExt(name));
}

function resourceUrl(path: string | null | undefined): string | undefined {
  return path ? `${FRONTEND_RESOURCES_PATH}/${path}` : undefined;
}

function stripExtension(fileName: string): string {
  return fileName.replace(/\.[^.]+$/, "");
}

/** An untitled track's name: its file's, numbered among the file's songs. */
function fallbackTitle(fileName: string, track?: number | null): string {
  const name = stripExtension(fileName);
  return track && isChiptuneFile(fileName) ? `${name} #${track}` : name;
}

function joinParts(parts: (string | null | undefined)[]): string {
  return parts.filter(Boolean).join(" · ");
}

/** A ROM's own soundtrack, one track per song, ordered by file name. */
export function panelTracksFromRom(
  rom: DetailedRom,
  songsByFileId: Map<number, TrackMetaSchema[]>,
  gameArtworkUrl?: string,
): PanelTrack[] {
  const files = rom.files ?? [];
  const fileUrl = (id?: number | null) => {
    const file = id ? files.find((f) => f.id === id) : undefined;
    return file ? romFileUrl(file.id, file.file_name) : undefined;
  };
  return files
    .filter(
      (file) => file.category === "soundtrack" && isAudioFile(file.file_name),
    )
    .slice()
    .sort((a, b) => a.file_name.localeCompare(b.file_name))
    .flatMap((file) => {
      const songs = songsByFileId.get(file.id);
      return (songs?.length ? songs : [undefined]).map((meta) => {
        const song = meta?.song ?? 0;
        return {
          id: file.id,
          song,
          key: playerTrackKey({ fileId: file.id, song }),
          romId: rom.id,
          fileName: file.file_name,
          title: meta?.title ?? fallbackTitle(file.file_name, meta?.track),
          subtitle: joinParts([meta?.artist, meta?.album]),
          url: romFileUrl(file.id, file.file_name),
          m3uUrl: fileUrl(meta?.m3u_file_id),
          durationSeconds: meta?.duration_seconds ?? undefined,
          fileSizeBytes: file.file_size_bytes,
          coverUrl: resourceUrl(meta?.cover_path),
          gameArtworkUrl,
          meta,
        };
      });
    });
}

/** Catalog tracks, which already carry their metadata and game context. */
export function panelTracksFromCatalog(
  tracks: MusicTrackSchema[],
): PanelTrack[] {
  return tracks.map((track) => {
    const title = track.title || fallbackTitle(track.file_name, track.track);
    const song = track.song ?? 0;
    return {
      id: track.rom_file_id,
      song,
      key: playerTrackKey({ fileId: track.rom_file_id, song }),
      romId: track.rom_id,
      fileName: track.file_name,
      title,
      // The game name is context only when it says something new: untagged
      // rips often reuse it as the title, and tagged ones as the album.
      subtitle: joinParts([
        track.artist,
        track.album,
        track.game_name === title || track.game_name === track.album
          ? null
          : track.game_name,
        track.platform_name,
      ]),
      url: track.stream_url,
      m3uUrl: track.m3u_url ?? undefined,
      durationSeconds: track.duration_seconds ?? undefined,
      coverUrl: track.cover_url ?? undefined,
      gameArtworkUrl: track.game_cover_url ?? undefined,
      meta: track,
    };
  });
}

/** The first cover image sitting alongside a ROM's soundtrack files. */
export function romFolderCoverUrl(rom: DetailedRom): string | undefined {
  const cover = (rom.files ?? [])
    .filter(
      (file) => file.category === "soundtrack" && isCoverFile(file.file_name),
    )
    .sort((a, b) => a.file_name.localeCompare(b.file_name))[0];
  return cover ? romFileUrl(cover.id, cover.file_name) : undefined;
}

/** The audio tags the now-playing surfaces show, from either track source. */
export type NowPlayingTags = Partial<
  Pick<
    TrackMetaSchema,
    "artist" | "album" | "genre" | "year" | "track" | "disc"
  >
>;

/** The line under a now-playing title: the album, else the artist. */
export function nowPlayingCaption(tags: NowPlayingTags | undefined): string {
  return tags?.album || tags?.artist || "";
}

/** The mini player's cover: the track's own art, then the ROM's. */
export function playerCoverUrl(meta: PlayerMeta): string {
  return (
    meta.coverUrl ||
    meta.folderCoverUrl ||
    meta.gameArtworkUrl ||
    "/assets/default/album_cover.jpg"
  );
}
