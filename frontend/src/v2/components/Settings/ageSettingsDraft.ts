import { ref } from "vue";
import { sameIds } from "@/v2/utils/lists";

export interface AgeSettings {
  ageLimit: number | null;
  hideUnrated: boolean | null;
  exemptRomIds: number[];
}

const EMPTY: AgeSettings = {
  ageLimit: null,
  hideUnrated: null,
  exemptRomIds: [],
};

function copy(settings: AgeSettings): AgeSettings {
  return { ...settings, exemptRomIds: [...settings.exemptRomIds] };
}

/** A dialog's editable age settings, and what changed since they loaded. */
export function createAgeSettingsDraft() {
  const draft = ref<AgeSettings>(copy(EMPTY));
  let loaded = EMPTY;

  function load(settings: AgeSettings = EMPTY, hiddenRomIds: number[] = []) {
    loaded = copy(settings);
    draft.value = copy(settings);
    // A hide beats an allow, so a game in both loads as hidden and the next
    // save drops its allow.
    draft.value.exemptRomIds = settings.exemptRomIds.filter(
      (id) => !hiddenRomIds.includes(id),
    );
  }

  function changes() {
    const { ageLimit, hideUnrated, exemptRomIds } = draft.value;
    return {
      settings:
        ageLimit !== loaded.ageLimit || hideUnrated !== loaded.hideUnrated,
      exemptions: !sameIds(exemptRomIds, loaded.exemptRomIds),
    };
  }

  return { draft, load, changes };
}
