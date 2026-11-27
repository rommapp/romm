import type { SimpleRomSchema } from "@/__generated__";

export type RomFieldName = keyof SimpleRomSchema;

/** A field the server leaves out of the response. */
export type OmittedRomFieldName = `-${RomFieldName}`;

/** The `fields` of a rom list: the names to return, or the names to leave
 * out. One request cannot hold both. */
export type RomFieldSelection =
  ReadonlySet<RomFieldName> | ReadonlySet<OmittedRomFieldName>;

/** Exactly these fields, plus `id`. With no list, only the ids. */
export const getFieldsWith = <K extends RomFieldName>(
  keys: readonly K[] = [],
): ReadonlySet<K> => new Set(keys);

/** The fields in `a`, `b` or both. */
export const union = <A extends RomFieldName, B extends RomFieldName>(
  a: ReadonlySet<A>,
  b: ReadonlySet<B>,
): ReadonlySet<A | B> => new Set<A | B>([...a, ...b]);

/** What `GameCover` reads to pick and draw a cover; see `CoverArtRom`. */
export const COVER_ART_FIELDS = getFieldsWith([
  "ss_metadata",
  "gamelist_metadata",
  "launchbox_metadata",
  "path_cover_large",
  "path_cover_small",
  "url_cover",
  "path_video",
  "platform_slug",
]);

/** What a row that shows a game's cover and name reads. */
export const COVER_AND_NAME_FIELDS = union(
  COVER_ART_FIELDS,
  getFieldsWith(["name", "fs_name"]),
);

const GALLERY_OMITTED = [
  "-igdb_metadata",
  "-moby_metadata",
  "-hasheous_metadata",
  "-flashpoint_metadata",
  "-demozoo_metadata",
  "-pouet_metadata",
  "-csdb_metadata",
  "-steam_metadata",
  "-crc_hash",
  "-md5_hash",
  "-sha1_hash",
  "-ra_hash",
  "-title_id",
  "-save_target",
  "-save_target_layout",
  "-full_path",
  "-upc",
  "-revision",
  "-version",
  "-is_physical",
  "-missing_from_fs",
  "-has_manual",
  "-path_manual",
  "-url_manual",
  "-has_soundtrack",
  "-youtube_video_id",
  "-merged_screenshots",
  "-merged_ra_metadata",
  "-alternative_names",
  "-tags",
  "-slug",
  "-has_notes",
] as const satisfies readonly OmittedRomFieldName[];

/** Every field but the ones only the details page and firmware code read. The
 * edit and match dialogs open with a gallery rom, so it keeps what they show
 * and save. */
export const GALLERY_FIELDS: ReadonlySet<(typeof GALLERY_OMITTED)[number]> =
  new Set(GALLERY_OMITTED);
