import { ref } from "vue";

export interface AgeSettings {
  ageLimit: number | null;
  hideUnrated: boolean | null;
}

const EMPTY: AgeSettings = { ageLimit: null, hideUnrated: null };

/** A dialog's editable age settings, and whether they changed since they loaded. */
export function createAgeSettingsDraft() {
  const draft = ref<AgeSettings>({ ...EMPTY });
  let loaded = EMPTY;

  function load(settings: AgeSettings = EMPTY) {
    loaded = { ...settings };
    draft.value = { ...settings };
  }

  function changed(): boolean {
    return (
      draft.value.ageLimit !== loaded.ageLimit ||
      draft.value.hideUnrated !== loaded.hideUnrated
    );
  }

  return { draft, load, changed };
}
