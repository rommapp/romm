import { useLocalStorage } from "@vueuse/core";
import type { RemovableRef } from "@vueuse/core";
import { storeToRefs } from "pinia";
import { effectScope, watch, ref } from "vue";
import type { UserSchema } from "@/__generated__";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";

export const UI_SETTINGS_KEYS = {
  // Language
  locale: { key: "settings.locale", default: "" },

  // Theme
  theme: { key: "settings.theme", default: "auto" },

  // NOTE: uiVersion is intentionally NOT tracked here. It's owned by the
  // singleton in composables/useUiVersion.ts so a write propagates reactively
  // to the RomM.vue gate without a reload. When v2 graduates we can move it
  // into this map and pick up backend sync.

  // Home section
  showStats: { key: "settings.showStats", default: true },
  showRecentRoms: { key: "settings.showRecentRoms", default: true },
  showContinuePlaying: { key: "settings.showContinuePlaying", default: true },
  showPlatforms: { key: "settings.showPlatforms", default: true },
  showCollections: { key: "settings.showCollections", default: true },

  // Home widget bar (v2 only). `showHomeWidgets` is the master toggle
  // for the row; per-widget toggles let users disable individual cards
  // without losing the rest. `librarySnapshotMode` chooses between the
  // compact (3 metrics) and extended (full v1-style: saves/states/
  // screenshots/disk) view of the Library Snapshot widget.
  showHomeWidgets: { key: "settings.showHomeWidgets", default: true },
  widgetRandomPick: { key: "settings.widgetRandomPick", default: true },
  widgetLibraryStats: {
    key: "settings.widgetLibraryStats",
    default: true,
  },
  libraryStatsMode: {
    key: "settings.libraryStatsMode",
    default: "compact",
  },
  // Widget render order — comma-separated list of widget IDs.
  // Persisted as a string in localStorage (the useUISettings helper
  // only handles primitives; consumers parse/serialize at the edges).
  // Unknown IDs are filtered out on read so removing a widget from
  // the registry doesn't leave dangling entries in user storage.
  widgetOrder: {
    key: "settings.widgetOrder",
    default: "randomPick,libraryStats",
  },

  // Platforms drawer
  platformsGroupBy: { key: "settings.platformsGroupBy", default: null },

  // Gallery section
  groupRoms: { key: "settings.groupRoms", default: true },
  showSiblings: { key: "settings.showSiblings", default: true },
  showRegions: { key: "settings.showRegions", default: true },
  showLanguages: { key: "settings.showLanguages", default: true },
  showStatus: { key: "settings.showStatus", default: true },
  showActionBar: { key: "settings.showActionBar", default: false },
  showGameTitle: { key: "settings.showGameTitle", default: false },
  enable3DEffect: { key: "settings.enable3DEffect", default: false },
  disableAnimations: { key: "settings.disableAnimations", default: false },
  enableExperimentalCache: {
    key: "settings.enableExperimentalCache",
    default: false,
  },
  boxartStyle: { key: "settings.boxartStyle", default: "cover_path" },

  // Gameplay
  // Ask for confirmation before launching a game the user deliberately
  // shelved (Retired / Never Playing) so an accidental Play doesn't
  // silently reactivate it.
  confirmProtectedLaunch: {
    key: "settings.confirmProtectedLaunch",
    default: true,
  },

  // Virtual collections
  showVirtualCollections: {
    key: "settings.showVirtualCollections",
    default: true,
  },
  virtualCollectionType: {
    key: "settings.virtualCollectionType",
    default: "collection",
  },
} as const;

export type UISettingsKey = keyof typeof UI_SETTINGS_KEYS;

// Helper type to extract the default value type for each setting
// Widens literal types to their base types (e.g., true -> boolean, "auto" -> string)
type WidenLiteral<T> = T extends string
  ? string
  : T extends number
    ? number
    : T extends boolean
      ? boolean
      : T extends null
        ? string | null
        : T;

type UISettingDefaultType<K extends UISettingsKey> = WidenLiteral<
  (typeof UI_SETTINGS_KEYS)[K]["default"]
>;

// Strongly-typed refs for each UI setting
type UISettingsRefs = {
  [K in UISettingsKey]: RemovableRef<UISettingDefaultType<K>>;
};

// Singleton state to prevent multiple instances
let uiSettingsInstance: ReturnType<typeof createUISettings> | null = null;
const isSyncing = ref(false); // Global flag to prevent sync loops

function createUISettings() {
  const authStore = storeAuth();
  const { user } = storeToRefs(authStore);

  // Get all localStorage refs
  const localStorageRefs = Object.fromEntries(
    Object.entries(UI_SETTINGS_KEYS).map(([name, config]) => [
      name,
      useLocalStorage(config.key, config.default),
    ]),
  ) as UISettingsRefs;

  // Initialize settings from backend user data
  function initialize() {
    const userWithSettings = user.value as UserSchema | null;
    if (!userWithSettings?.ui_settings) return;

    isSyncing.value = true;
    const backendSettings = userWithSettings.ui_settings;

    // Sync backend settings to localStorage
    Object.entries(localStorageRefs).forEach(([key, ref]) => {
      if (key in backendSettings) {
        ref.value = backendSettings[key as UISettingsKey];
      }
    });

    // Use nextTick-like delay to ensure all updates are done
    setTimeout(() => {
      isSyncing.value = false;
    }, 50);
  }

  // Collect current settings from localStorage
  function collectSettings(): Record<string, unknown> {
    return Object.fromEntries(
      Object.entries(localStorageRefs).map(([key, ref]) => [key, ref.value]),
    );
  }

  const saveUISettings = async () => {
    if (!user.value || isSyncing.value) return;

    const currentSettings = collectSettings();

    try {
      const { data } = await userApi.updateUser({
        id: user.value.id,
        ui_settings: JSON.stringify(currentSettings),
      } as Partial<UserSchema> & { ui_settings: string });

      // Update the user in the store with the new settings (without triggering sync)
      isSyncing.value = true;
      const dataWithSettings = data as UserSchema;
      if (dataWithSettings.ui_settings) {
        authStore.setCurrentUser(data);
      }
      setTimeout(() => {
        isSyncing.value = false;
      }, 50);
    } catch (error) {
      console.error("Failed to save UI settings to backend:", error);
    }
  };

  // Watch all localStorage refs for changes (only set up once)
  Object.values(localStorageRefs).forEach((ref) => {
    watch(ref, () => {
      if (!isSyncing.value) {
        saveUISettings();
      }
    });
  });

  // Watch user changes to initialize settings
  watch(
    user,
    (newUser) => {
      const userWithSettings = newUser as UserSchema | null;
      if (userWithSettings?.ui_settings) {
        initialize();
      }
    },
    { immediate: true },
  );

  return {
    ...localStorageRefs,
    initialize: initialize,
    saveUISettings: () => saveUISettings(),
  };
}

export function useUISettings() {
  // Return singleton instance
  if (!uiSettingsInstance) {
    uiSettingsInstance = effectScope(true).run(createUISettings)!;
  }
  return uiSettingsInstance;
}
