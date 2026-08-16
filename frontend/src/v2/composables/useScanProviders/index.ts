// useScanProviders: the provider + hash-matcher model shared by every
// surface that launches a scan (the /scan view, the per-platform scan
// dialog, the per-ROM refresh dialog), so all three send the backend the
// same payload for the same choices.
//
// Hash matchers are proxies, not catalogs: they match files by hash and
// feed IDs into the primary catalogs. Hasheous rides along in `apis`
// (backend gate: `MetadataSource.HASHEOUS in apis`); Playmatch has no enum
// entry and uses the separate `playmatch_enabled` flag (backend gate:
// `playmatch_enabled and IGDB in apis`), hence its IGDB requirement.
//
// A group's RSelect treats an empty model as "All", so an All-mode group
// contributes nothing to `metadataSources`, while the backend reads an
// empty `apis` list as "no sources". `effectiveMetadataSources` bridges
// that by expanding an All-mode group to its enabled providers.
import { useLocalStorage, type RemovableRef } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { computed, ref, watch, type ComputedRef, type Ref } from "vue";
import { useI18n } from "vue-i18n";
import storeConfig from "@/stores/config";
import storeHeartbeat, { type MetadataOption } from "@/stores/heartbeat";

const LOCAL_STORAGE_METADATA_SOURCES_KEY = "scan.metadataSources";
const LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY =
  "scan.launchboxRemoteEnabled";
const LOCAL_STORAGE_HASHEOUS_ENABLED_KEY = "scan.hasheousEnabled";
const LOCAL_STORAGE_PLAYMATCH_ENABLED_KEY = "scan.playmatchEnabled";

const HASH_MATCHER_KEYS = ["hasheous", "playmatch"] as const;

// Mirrors the split used by the setup wizard's metadata step: general
// catalogs ship a full game record, specific sources add one dimension.
const GENERAL_PROVIDER_KEYS = new Set([
  "igdb",
  "ss",
  "moby",
  "launchbox",
  "flashpoint",
  "gamelist",
  "libretro",
]);
const SPECIFIC_PROVIDER_KEYS = new Set(["ra", "sgdb", "hltb"]);

export type HashMatcherKey = (typeof HASH_MATCHER_KEYS)[number];

export interface HashMatcher {
  value: HashMatcherKey;
  name: string;
  logo: string;
  /** Reason the switch is forced off, surfaced in the hover tooltip.
   *  null when the switch is interactable. */
  blockedReason: string | null;
  switchEnabled: boolean;
}

export interface ScanPayload {
  apis: string[];
  launchbox_remote_enabled: boolean;
  playmatch_enabled: boolean;
}

export interface UseScanProviders {
  calculateHashes: ComputedRef<boolean>;
  generalProviders: ComputedRef<MetadataOption[]>;
  specificProviders: ComputedRef<MetadataOption[]>;
  /** Explicit picks, shared as the v-model of both provider selects. */
  metadataSources: Ref<MetadataOption[]>;
  /** Picks with All-mode groups expanded, i.e. what the scan uses. */
  effectiveMetadataSources: ComputedRef<MetadataOption[]>;
  /** Bind to each select's `@update:all-selected`. */
  generalAllSelected: Ref<boolean>;
  specificAllSelected: Ref<boolean>;
  isLaunchboxSelected: ComputedRef<boolean>;
  launchboxRemoteEnabled: RemovableRef<boolean>;
  hashMatchers: ComputedRef<HashMatcher[]>;
  setHashMatcher: (value: HashMatcherKey, next: boolean) => void;
  isHashMatcherOn: (matcher: HashMatcher) => boolean;
  buildScanPayload: () => ScanPayload;
  persistSelection: () => void;
}

export function useScanProviders(): UseScanProviders {
  const { t } = useI18n();
  const heartbeat = storeHeartbeat();
  const configStore = storeConfig();
  const { config } = storeToRefs(configStore);

  const calculateHashes = computed(() => !config.value.SKIP_HASH_CALCULATION);

  // Catalog options: main metadata sources, minus the hash matchers.
  const metadataOptions = computed(() =>
    heartbeat
      .getMetadataOptionsByPriority()
      .filter(
        (option) =>
          !(HASH_MATCHER_KEYS as readonly string[]).includes(option.value),
      )
      .map((option) => {
        const requiresHashes = option.value === "ra";
        let disabled = option.disabled;
        if (!calculateHashes.value && requiresHashes) {
          disabled = t("scan.requires-hashes", { source: option.name });
        }
        return { ...option, disabled };
      }),
  );

  const generalProviders = computed<MetadataOption[]>(() =>
    metadataOptions.value.filter((o) => GENERAL_PROVIDER_KEYS.has(o.value)),
  );
  const specificProviders = computed<MetadataOption[]>(() =>
    metadataOptions.value.filter((o) => SPECIFIC_PROVIDER_KEYS.has(o.value)),
  );
  const enabledGeneralProviders = computed(() =>
    generalProviders.value.filter((o) => !o.disabled),
  );
  const enabledSpecificProviders = computed(() =>
    specificProviders.value.filter((o) => !o.disabled),
  );

  const storedMetadataSources = useLocalStorage(
    LOCAL_STORAGE_METADATA_SOURCES_KEY,
    [] as string[],
  );
  const launchboxRemoteEnabled = useLocalStorage(
    LOCAL_STORAGE_LAUNCHBOX_REMOTE_ENABLED_KEY,
    true,
  );
  const hasheousEnabled = useLocalStorage(
    LOCAL_STORAGE_HASHEOUS_ENABLED_KEY,
    true,
  );
  const playmatchEnabled = useLocalStorage(
    LOCAL_STORAGE_PLAYMATCH_ENABLED_KEY,
    true,
  );

  // A group with no pick stays empty, which the selects read as All.
  const metadataSources = ref<MetadataOption[]>([]);
  watch(
    [metadataOptions, storedMetadataSources],
    ([options, stored], previous) => {
      // A new stored list (written by whichever surface last scanned)
      // replaces the picks. When only the option list moved (a heartbeat
      // refresh, an admin toggle), keep the current picks and just drop the
      // ones that went away, so an in-progress selection survives.
      const storedChanged = !previous || previous[1] !== stored;
      metadataSources.value = storedChanged
        ? options.filter((o) => stored.includes(o.value) && !o.disabled)
        : metadataSources.value
            .map((s) => options.find((o) => o.value === s.value && !o.disabled))
            .filter((o): o is MetadataOption => Boolean(o));
    },
    { immediate: true },
  );

  function hasGroupSelection(keys: Set<string>): boolean {
    return metadataSources.value.some((s) => keys.has(s.value));
  }

  // All-mode mirrors of each select, initialised the way the primitive does
  // (no own selection ⇒ All) and kept in sync via `@update:all-selected`.
  const generalAllSelected = ref(!hasGroupSelection(GENERAL_PROVIDER_KEYS));
  const specificAllSelected = ref(!hasGroupSelection(SPECIFIC_PROVIDER_KEYS));

  // An explicit pick always wins over the All flag: the two are mutually
  // exclusive in the select, and reading the model keeps us right even
  // before a select has mounted to emit its initial state.
  function resolveGroup(
    keys: Set<string>,
    allSelected: boolean,
    enabled: MetadataOption[],
  ): MetadataOption[] {
    const picked = metadataSources.value.filter((s) => keys.has(s.value));
    if (picked.length > 0) return picked;
    return allSelected ? enabled : [];
  }

  const effectiveMetadataSources = computed<MetadataOption[]>(() => [
    ...resolveGroup(
      GENERAL_PROVIDER_KEYS,
      generalAllSelected.value,
      enabledGeneralProviders.value,
    ),
    ...resolveGroup(
      SPECIFIC_PROVIDER_KEYS,
      specificAllSelected.value,
      enabledSpecificProviders.value,
    ),
  ]);

  const isLaunchboxSelected = computed(() =>
    effectiveMetadataSources.value.some((s) => s.value === "launchbox"),
  );

  const hashMatchers = computed<HashMatcher[]>(() => {
    const sources = heartbeat.value.METADATA_SOURCES;
    const igdbSelected = effectiveMetadataSources.value.some(
      (s) => s.value === "igdb",
    );
    const noHashes = !calculateHashes.value;

    const hasheousAdmin = Boolean(sources?.HASHEOUS_API_ENABLED);
    const playmatchAdmin = Boolean(sources?.PLAYMATCH_API_ENABLED);

    return [
      {
        value: "hasheous",
        name: "Hasheous",
        logo: "/assets/scrappers/hasheous.png",
        blockedReason: !hasheousAdmin
          ? t("scan.disabled-by-admin")
          : noHashes
            ? t("scan.requires-hashes", { source: "Hasheous" })
            : null,
        switchEnabled: hasheousAdmin && !noHashes,
      },
      {
        value: "playmatch",
        name: "Playmatch",
        logo: "/assets/scrappers/playmatch.png",
        blockedReason: !playmatchAdmin
          ? t("scan.disabled-by-admin")
          : noHashes
            ? t("scan.requires-hashes", { source: "Playmatch" })
            : !igdbSelected
              ? t("scan.playmatch-requires-igdb")
              : null,
        switchEnabled: playmatchAdmin && !noHashes && igdbSelected,
      },
    ];
  });

  function setHashMatcher(value: HashMatcherKey, next: boolean) {
    if (value === "hasheous") hasheousEnabled.value = next;
    else playmatchEnabled.value = next;
  }

  function isHashMatcherOn(matcher: HashMatcher): boolean {
    if (!matcher.switchEnabled) return false;
    return matcher.value === "hasheous"
      ? hasheousEnabled.value
      : playmatchEnabled.value;
  }

  function isOn(value: HashMatcherKey): boolean {
    const matcher = hashMatchers.value.find((m) => m.value === value);
    return matcher ? isHashMatcherOn(matcher) : false;
  }

  function buildScanPayload(): ScanPayload {
    const apis = effectiveMetadataSources.value.map((s) => s.value);
    if (isOn("hasheous")) apis.push("hasheous");
    return {
      apis,
      launchbox_remote_enabled: launchboxRemoteEnabled.value,
      playmatch_enabled: isOn("playmatch"),
    };
  }

  // Persist the explicit picks, not the expanded list: an All-mode group
  // stores nothing so it keeps meaning "everything", including providers
  // enabled later.
  function persistSelection() {
    storedMetadataSources.value = metadataSources.value.map((s) => s.value);
  }

  return {
    calculateHashes,
    generalProviders,
    specificProviders,
    metadataSources,
    effectiveMetadataSources,
    generalAllSelected,
    specificAllSelected,
    isLaunchboxSelected,
    launchboxRemoteEnabled,
    hashMatchers,
    setHashMatcher,
    isHashMatcherOn,
    buildScanPayload,
    persistSelection,
  };
}
