import { computed, toValue, type MaybeRefOrGetter } from "vue";
import { useI18n } from "vue-i18n";
import type { SaveSchema, StateSchema } from "@/__generated__";
import type { SliderBtnGroupItem } from "@/v2/lib/primitives/RSliderBtnGroup/types";
import { isCoreCompatible, type AssetType } from "@/v2/utils/assets";

/**
 * The Saves / States tabs of an EmulatorJS picker, with states counted and
 * disabled against the core that would load them.
 */
export function useSaveStateTabs(
  saves: MaybeRefOrGetter<SaveSchema[]>,
  states: MaybeRefOrGetter<StateSchema[]>,
  core: MaybeRefOrGetter<string | null>,
) {
  const { t } = useI18n();

  const stateCount = computed(() => toValue(states).length);
  const compatibleStates = computed(() =>
    toValue(states).filter((state) => isCoreCompatible(state, toValue(core))),
  );
  const allStatesCompatible = computed(
    () => compatibleStates.value.length === stateCount.value,
  );

  const tabs = computed<SliderBtnGroupItem<AssetType>[]>(() => [
    {
      id: "save",
      label: t("common.saves"),
      badge: toValue(saves).length,
      icon: "mdi-content-save",
    },
    {
      id: "state",
      label: t("common.states"),
      badge: allStatesCompatible.value
        ? stateCount.value
        : `${compatibleStates.value.length}/${stateCount.value}`,
      icon: "mdi-file",
    },
  ]);

  // Other emulators' states stay listed, disabled, so the count adds up.
  function stateDisabledReason(asset: { emulator?: string | null }) {
    if (isCoreCompatible(asset, toValue(core))) return null;
    return t("play.state-incompatible-core", { emulator: asset.emulator });
  }

  return {
    tabs,
    stateCount,
    compatibleStates,
    allStatesCompatible,
    stateDisabledReason,
  };
}
