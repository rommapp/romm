// The provider taxonomy every metadata surface groups by: full-record
// catalogs, single-dimension specialised sources, and hash proxies that
// feed ids into the catalogs. Surfaces keep their own presentation data
// (logos, locale keys, links, heartbeat wiring) and read the group from
// here, so a new provider lands in the same group everywhere.
export type MetadataProviderGroup = "catalog" | "specialised" | "proxy";

/** Keyed by the slug the backend `MetadataSource` enum and the heartbeat
 *  store use, so a provider is looked up by the same id everywhere. */
export const METADATA_PROVIDER_GROUPS = {
  igdb: "catalog",
  ss: "catalog",
  moby: "catalog",
  launchbox: "catalog",
  flashpoint: "catalog",
  gamelist: "catalog",
  libretro: "catalog",
  ra: "specialised",
  sgdb: "specialised",
  hltb: "specialised",
  hasheous: "proxy",
  playmatch: "proxy",
} as const satisfies Record<string, MetadataProviderGroup>;

export type MetadataProviderKey = keyof typeof METADATA_PROVIDER_GROUPS;

/** The provider keys of one group, as a union. A consumer that holds
 *  per-provider state or config in a `Record` keyed by this gets a
 *  compile error when the group grows a member. */
export type MetadataProviderKeyIn<G extends MetadataProviderGroup> = {
  [K in MetadataProviderKey]: (typeof METADATA_PROVIDER_GROUPS)[K] extends G
    ? K
    : never;
}[MetadataProviderKey];

/** Section order shared by every surface that renders the groups. */
export const METADATA_PROVIDER_GROUP_ORDER = [
  "catalog",
  "specialised",
  "proxy",
] as const satisfies readonly MetadataProviderGroup[];

export function providerKeysInGroup<G extends MetadataProviderGroup>(
  group: G,
): MetadataProviderKeyIn<G>[] {
  return (
    Object.keys(METADATA_PROVIDER_GROUPS) as MetadataProviderKey[]
  ).filter(
    (key): key is MetadataProviderKeyIn<G> =>
      METADATA_PROVIDER_GROUPS[key] === group,
  );
}

/** Group of an unvalidated key (a heartbeat option value), or undefined
 *  when the provider is not part of the taxonomy. */
export function metadataProviderGroup(
  key: string,
): MetadataProviderGroup | undefined {
  return key in METADATA_PROVIDER_GROUPS
    ? METADATA_PROVIDER_GROUPS[key as MetadataProviderKey]
    : undefined;
}
