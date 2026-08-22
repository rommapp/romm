// The provider taxonomy every metadata surface groups by: full-record
// catalogs, single-dimension specialised sources, and hash proxies that
// feed ids into the catalogs.
export type MetadataProviderGroup = "catalog" | "specialised" | "proxy";

/** Keyed by the slug the backend `MetadataSource` enum and the heartbeat
 *  store use. */
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

/** The provider keys of one group, as a union, so a `Record` keyed by it
 *  fails to compile when the group grows a member. */
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

/** Section title and hint keys in the setup wizard's `setup.*` namespace,
 *  shared by the wizard step and the scan info dialog. */
export const SETUP_GROUP_LABELS: Record<
  MetadataProviderGroup,
  { titleKey: string; hintKey: string }
> = {
  catalog: {
    titleKey: "setup.metadata-catalogs",
    hintKey: "setup.metadata-catalogs-hint",
  },
  specialised: {
    titleKey: "setup.metadata-specialised",
    hintKey: "setup.metadata-specialised-hint",
  },
  proxy: {
    titleKey: "setup.metadata-proxies",
    hintKey: "setup.metadata-proxies-hint",
  },
};

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

/** Splits keyed providers into renderable sections, in section order,
 *  merging each group's presentation labels into its section. */
export function groupProviders<
  T extends { key: MetadataProviderKey },
  L extends object,
>(
  providers: readonly T[],
  labels: Record<MetadataProviderGroup, L>,
): ({ group: MetadataProviderGroup; providers: T[] } & L)[] {
  return METADATA_PROVIDER_GROUP_ORDER.map((group) => ({
    group,
    ...labels[group],
    providers: providers.filter(
      (provider) => METADATA_PROVIDER_GROUPS[provider.key] === group,
    ),
  }));
}

/** Group of an unvalidated key (a heartbeat option value), or undefined
 *  when the provider is not part of the taxonomy. */
export function metadataProviderGroup(
  key: string,
): MetadataProviderGroup | undefined {
  // Own-property check, so a prototype member ("toString") is not a group.
  return Object.hasOwn(METADATA_PROVIDER_GROUPS, key)
    ? METADATA_PROVIDER_GROUPS[key as MetadataProviderKey]
    : undefined;
}
