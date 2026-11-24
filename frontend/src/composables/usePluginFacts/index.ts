// usePluginFacts: what a plugin learned about the game on screen.
//
// A plugin declares a panel and the server reads its source, so this only asks
// and holds the answers: one request per plugin per game, shared by every action
// that wants to show what its report says. Keyed two ways on purpose — by the
// panel's id, and by the action it explains — because a button asks "what is my
// panel" while a page asks "what panels are there".
import { computed, ref, watch } from "vue";
import type { PluginFactSchema } from "@/__generated__";
import pluginApi from "@/services/api/plugin";
import { usePluginStore } from "@/stores/plugins";
import type { SimpleRom } from "@/stores/roms";

export function usePluginFacts(getRom: () => SimpleRom | null | undefined) {
  const store = usePluginStore();
  const facts = ref<Record<string, PluginFactSchema>>({});
  const loading = ref(false);
  const askedFor = ref<number | null>(null);
  // Guards a late reply: the answer only lands if it is still the game on
  // screen, and only once, so a slow source cannot replace a newer report.
  let generation = 0;

  const pluginsWithFacts = computed(() =>
    store.plugins.filter((plugin) => (plugin.facts ?? []).length > 0),
  );

  async function load(romId: number): Promise<void> {
    if (askedFor.value === romId) return;
    askedFor.value = romId;
    const mine = ++generation;
    // The report belongs to the game, so leaving one clears it rather than
    // showing the last game's numbers under this one's name.
    facts.value = {};
    if (!pluginsWithFacts.value.length) return;
    loading.value = true;
    const collected: Record<string, PluginFactSchema> = {};
    await Promise.all(
      pluginsWithFacts.value.map(async (plugin) => {
        try {
          const reply = await pluginApi.getFacts(plugin.id, romId);
          const byId = new Map(
            (reply.data?.facts ?? []).map((fact) => [fact.id, fact]),
          );
          for (const [factId, fact] of byId) {
            collected[`${plugin.id}:${factId}`] = fact;
          }
          // The manifest, not the answer, says which button a panel explains.
          for (const summary of plugin.facts ?? []) {
            const fact = byId.get(summary.id);
            if (fact && summary.action) {
              collected[`${plugin.id}:action:${summary.action}`] = fact;
            }
          }
        } catch {
          // A plugin that cannot answer is not worth an error of its own; its
          // buttons keep their plain labels.
        }
      }),
    );
    if (mine !== generation) return;
    facts.value = collected;
    loading.value = false;
  }

  // The shelf may finish loading after the page does, so the watch is on both
  // the game and whether there is anything to ask about: waiting only for the
  // game would leave the buttons without their reports on a cold start.
  watch(
    () => [getRom()?.id ?? null, pluginsWithFacts.value.length] as const,
    ([romId, withFacts]) => {
      if (romId && withFacts) void load(romId);
    },
    { immediate: true },
  );

  /** The panel that explains one action's button, if the manifest tied them. */
  function factForAction(
    pluginId: string,
    actionId: string,
  ): PluginFactSchema | null {
    return facts.value[`${pluginId}:action:${actionId}`] ?? null;
  }

  return { facts, loading, factForAction };
}
