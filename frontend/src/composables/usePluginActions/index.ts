import { computed, onMounted, type ComputedRef } from "vue";
import type { PluginActionSchema } from "@/__generated__";
import { usePluginStore } from "@/stores/plugins";
import type { SimpleRom } from "@/stores/roms";
import { getSoleRomFile } from "@/utils";

/** The icon a manifest that names none falls back to. */
export const DEFAULT_PLUGIN_ICON = "mdi-puzzle-outline";

/** One plugin action with its URL template filled in for this rom. */
export interface PluginAction extends PluginActionSchema {
  pluginId: string;
  pluginName: string;
  /** The template with every placeholder replaced by this rom's values. */
  href: string;
}

/** Fill a manifest's URL template with the rom the button was pressed on.
 *
 * Every value is encoded: a game called `Sonic & Knuckles` must not turn the
 * query string into a second parameter for whatever accepts the URL.
 *
 * Args:
 *   template: The manifest's `url`, placeholders unexpanded.
 *   rom: The rom the action is offered on.
 *
 * Returns:
 *   string: The URL to open.
 */
export function expandPluginUrl(
  template: string,
  rom: SimpleRom | null,
  settings: Record<string, unknown> = {},
): string {
  const values: Record<string, string> = {
    rom_id: rom ? String(rom.id) : "",
    rom_name: rom?.name ?? "",
    platform_slug: rom?.platform_slug ?? "",
    platform_name: rom?.platform_display_name ?? "",
    file_name: rom ? (getSoleRomFile(rom)?.file_name ?? "") : "",
  };
  // {setting.<key>} is what the plugin asked its user for. Whole-value use is
  // left unencoded so a URL fragment or query a plugin stores stays as it was
  // written; a placeholder inside a longer value is encoded like the rest.
  return template.replace(
    /\{(setting\.)?([a-z_]+)\}/g,
    (match, isSetting: string | undefined, key: string) => {
      if (!isSetting) return encodeURIComponent(values[key] ?? "");
      const value = settings[key];
      if (value === undefined || value === null) return "";
      return String(value);
    },
  );
}

/** Whether a setting that gates an action is switched on.
 *
 *  Only an explicit `false` closes the gate. A setting that has not been read
 *  yet is not a user saying no, and hiding a button the moment a page renders
 *  would make the same plugin appear on one page and not the next. */
export function gateOpen(
  enabledBy: string | null | undefined,
  settings: Record<string, unknown>,
): boolean {
  if (!enabledBy) return true;
  return settings[enabledBy] !== false;
}

/** Whether an action's platform list covers this rom. An empty list is every
 *  platform, and either slug a platform is known by counts.
 *
 * Args:
 *   platforms: The manifest's slugs.
 *   rom: The rom the action is offered on.
 *
 * Returns:
 *   boolean: True when the action belongs on this rom.
 */
export function offersPlatform(
  platforms: string[],
  rom: SimpleRom | null,
): boolean {
  if (!platforms?.length) return true;
  if (!rom) return false;
  const slugs = [rom.platform_slug, rom.platform_fs_slug]
    .filter((slug): slug is string => Boolean(slug))
    .map((slug) => slug.toLowerCase());
  return platforms.some((platform) => slugs.includes(platform.toLowerCase()));
}

/** The plugin actions offered on one rom, and the way to open them.
 *
 * Args:
 *   getRom: Resolver for the rom the actions belong to.
 */
export function usePluginActions(getRom: () => SimpleRom | null | undefined): {
  actions: ComputedRef<PluginAction[]>;
  playActions: ComputedRef<PluginAction[]>;
  forSlot: (slot: string) => PluginAction[];
  open: (action: PluginAction) => void;
} {
  const store = usePluginStore();
  onMounted(() => void store.load());

  const actions = computed<PluginAction[]>(() => {
    const rom = getRom() ?? null;
    return store.plugins.flatMap((plugin) => {
      const settings = store.settingsFor(plugin.id);
      return plugin.actions
        .filter((action) => offersPlatform(action.platforms ?? [], rom))
        .filter((action) => gateOpen(action.enabled_by, settings))
        .map((action) => ({
          ...action,
          icon: action.icon ?? DEFAULT_PLUGIN_ICON,
          pluginId: plugin.id,
          pluginName: plugin.name,
          href: expandPluginUrl(action.url, rom, settings),
        }));
    });
  });

  /** The actions for one surface: `game.details`, `game.play` and the rest. */
  function forSlot(slot: string): PluginAction[] {
    return actions.value.filter(
      (action) => (action.slot ?? "game.details") === slot,
    );
  }

  /** The actions that offer a way to start the game, for the Play menu. */
  const playActions = computed<PluginAction[]>(() => forSlot("game.play"));
  /** Hand the URL to the browser, which hands a custom scheme to the OS.
   *
   * Args:
   *   action: The action whose URL to open.
   */
  function open(action: PluginAction): void {
    if (action.open === "same-tab") {
      window.location.assign(action.href);
      return;
    }
    window.open(action.href, "_blank", "noopener,noreferrer");
  }

  return { actions, playActions, forSlot, open };
}
