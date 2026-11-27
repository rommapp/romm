import type { SimpleRomSchema } from "@/__generated__";

const NAMES = [
  "id",
  "igdb_id",
  "sgdb_id",
  "moby_id",
  "ss_id",
  "ra_id",
  "launchbox_id",
  "hasheous_id",
  "tgdb_id",
  "flashpoint_id",
  "hltb_id",
  "demozoo_id",
  "pouet_id",
  "csdb_id",
  "steam_id",
  "gamelist_id",
  "libretro_id",
  "platform_id",
  "platform_slug",
  "platform_fs_slug",
  "platform_custom_name",
  "platform_display_name",
  "fs_name",
  "fs_name_no_tags",
  "fs_name_no_ext",
  "fs_extension",
  "fs_path",
  "fs_size_bytes",
  "name",
  "name_sort_key",
  "slug",
  "summary",
  "alternative_names",
  "youtube_video_id",
  "metadatum",
  "igdb_metadata",
  "moby_metadata",
  "ss_metadata",
  "launchbox_metadata",
  "hasheous_metadata",
  "flashpoint_metadata",
  "hltb_metadata",
  "demozoo_metadata",
  "pouet_metadata",
  "csdb_metadata",
  "steam_metadata",
  "gamelist_metadata",
  "manual_metadata",
  "path_cover_small",
  "path_cover_large",
  "url_cover",
  "has_manual",
  "has_soundtrack",
  "path_manual",
  "url_manual",
  "path_video",
  "is_identifying",
  "is_unidentified",
  "is_identified",
  "revision",
  "version",
  "regions",
  "languages",
  "tags",
  "crc_hash",
  "md5_hash",
  "sha1_hash",
  "ra_hash",
  "title_id",
  "save_target",
  "save_target_layout",
  "has_simple_single_file",
  "has_nested_single_file",
  "has_multiple_files",
  "is_easyrpg_game",
  "has_jsdos_bundle",
  "full_path",
  "created_at",
  "updated_at",
  "missing_from_fs",
  "is_physical",
  "has_file_on_disk",
  "upc",
  "has_notes",
  "rom_user",
  "merged_screenshots",
  "merged_ra_metadata",
  "sibling_roms",
  "screenshot_path",
] as const satisfies readonly (keyof SimpleRomSchema)[];

type DefaultField = (typeof NAMES)[number];

/** Every `SimpleRomSchema` field except `files`, which a rom list leaves empty
 * unless it is asked for. Sending all of them returns the same response as
 * sending no `fields`. */
export const DEFAULT_ROM_FIELDS: ReadonlySet<DefaultField> = new Set(NAMES);

/** Exactly these fields, plus `id`. With no list, only the ids. */
export const getFieldsWith = <K extends keyof SimpleRomSchema>(
  keys: readonly K[] = [],
): ReadonlySet<K> => new Set(keys);

/** The fields in `a`, `b` or both. */
export const union = <
  A extends keyof SimpleRomSchema,
  B extends keyof SimpleRomSchema,
>(
  a: ReadonlySet<A>,
  b: ReadonlySet<B>,
): ReadonlySet<A | B> => new Set<A | B>([...a, ...b]);

/** The fields in both `a` and `b`. */
export const intersection = <
  A extends keyof SimpleRomSchema,
  B extends keyof SimpleRomSchema,
>(
  a: ReadonlySet<A>,
  b: ReadonlySet<B>,
): ReadonlySet<Extract<A, B>> =>
  new Set(
    [...a].filter((field): field is Extract<A, B> =>
      b.has(field as unknown as B),
    ),
  );

/** The fields in `a` that are not in `b`. */
export const difference = <
  A extends keyof SimpleRomSchema,
  B extends keyof SimpleRomSchema,
>(
  a: ReadonlySet<A>,
  b: ReadonlySet<B>,
): ReadonlySet<Exclude<A, B>> =>
  new Set(
    [...a].filter(
      (field): field is Exclude<A, B> => !b.has(field as unknown as B),
    ),
  );

/** Every default field except these. */
export const getFieldsWithout = <D extends DefaultField>(
  drop: readonly D[],
): ReadonlySet<Exclude<DefaultField, D>> =>
  difference(DEFAULT_ROM_FIELDS, getFieldsWith(drop));

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

/** What a gallery card or list row reads: every default field except those
 * only the details page, dialogs and firmware code use. */
export const GALLERY_FIELDS = getFieldsWithout([
  "igdb_metadata",
  "moby_metadata",
  "hasheous_metadata",
  "flashpoint_metadata",
  "demozoo_metadata",
  "pouet_metadata",
  "csdb_metadata",
  "steam_metadata",
  "crc_hash",
  "md5_hash",
  "sha1_hash",
  "ra_hash",
  "title_id",
  "save_target",
  "save_target_layout",
  "fs_path",
  "full_path",
  "upc",
  "revision",
  "version",
  "is_physical",
  "missing_from_fs",
  "sgdb_id",
  "tgdb_id",
  "has_manual",
  "path_manual",
  "url_manual",
  "has_soundtrack",
  "youtube_video_id",
  "merged_screenshots",
  "merged_ra_metadata",
  "manual_metadata",
  "alternative_names",
  "tags",
  "slug",
  "has_notes",
  "has_multiple_files",
]);
