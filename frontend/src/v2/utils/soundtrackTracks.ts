// The one track shape the soundtrack player renders; both sources (a ROM's
// own files, the music catalog) normalize into it here.
import type { MusicTrackSchema, TrackMetaSchema } from "@/__generated__";
import type { DetailedRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

export interface PanelTrack {
  /** `rom_file_id` — unique across the catalog. */
  id: number;
  romId: number;
  fileName: string;
  /** Display title, already resolved from metadata or the file name. */
  title: string;
  /** Artist · album · (game · platform) — whatever the source could supply. */
  subtitle: string;
  url: string;
  durationSeconds?: number;
  fileSizeBytes?: number;
  coverUrl?: string;
  gameArtworkUrl?: string;
  meta?: TrackMetaSchema;
}

const AUDIO_EXTS = new Set(["mp3", "ogg", "oga", "wav", "flac", "m4a", "opus"]);
const COVER_EXTS = new Set(["jpg", "jpeg", "png", "webp", "gif"]);

export function getExt(name: string): string {
  const dot = name.lastIndexOf(".");
  return dot === -1 ? "" : name.slice(dot + 1).toLowerCase();
}

export function isAudioFile(name: string): boolean {
  return AUDIO_EXTS.has(getExt(name));
}

export function isCoverFile(name: string): boolean {
  return COVER_EXTS.has(getExt(name));
}

export function romFileUrl(fileId: number, fileName: string): string {
  return `/api/roms/${fileId}/files/content/${encodeURIComponent(fileName)}`;
}

function resourceUrl(path: string | null | undefined): string | undefined {
  return path ? `${FRONTEND_RESOURCES_PATH}/${path}` : undefined;
}

function stripExtension(fileName: string): string {
  return fileName.replace(/\.[^.]+$/, "");
}

function joinParts(parts: (string | null | undefined)[]): string {
  return parts.filter(Boolean).join(" · ");
}

/** A ROM's own soundtrack files, ordered by file name. */
export function panelTracksFromRom(
  rom: DetailedRom,
  metaByFileId: Map<number, TrackMetaSchema>,
  gameArtworkUrl?: string,
): PanelTrack[] {
  return (rom.files ?? [])
    .filter(
      (file) => file.category === "soundtrack" && isAudioFile(file.file_name),
    )
    .slice()
    .sort((a, b) => a.file_name.localeCompare(b.file_name))
    .map((file) => {
      const meta = metaByFileId.get(file.id);
      return {
        id: file.id,
        romId: rom.id,
        fileName: file.file_name,
        title: meta?.title ?? stripExtension(file.file_name),
        subtitle: joinParts([meta?.artist, meta?.album]),
        url: romFileUrl(file.id, file.file_name),
        durationSeconds: meta?.duration_seconds ?? undefined,
        fileSizeBytes: file.file_size_bytes,
        coverUrl: resourceUrl(meta?.cover_path),
        gameArtworkUrl,
        meta,
      };
    });
}

/** Catalog tracks, which already carry their metadata and game context. */
export function panelTracksFromCatalog(
  tracks: MusicTrackSchema[],
): PanelTrack[] {
  return tracks.map((track) => {
    const title = track.title || stripExtension(track.game_name ?? "");
    return {
      id: track.rom_file_id,
      romId: track.rom_id,
      fileName: track.title || track.game_name || String(track.rom_file_id),
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
