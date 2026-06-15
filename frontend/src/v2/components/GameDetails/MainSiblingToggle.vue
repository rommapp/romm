<script setup lang="ts">
// MainSiblingToggle — marks this rom as the "default version" of the
// sibling group: when the gallery groups siblings, the main one is the
// card that's shown in the user's library. Per-user state — every user
// picks their own preferred version.
//
// The backend enforces the exclusive constraint (setting this one to
// true flips the rest of the group to false), so the UI doesn't need
// to mutate other siblings client-side.
//
// Optimistic write follows the useGameActions pattern: flip locally,
// PUT to the server, revert + snackbar on failure.
import { RBtn, RIcon } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { RomUserData } from "@/__generated__";
import romApi from "@/services/api/rom";
import storeRoms from "@/stores/roms";
import type { DetailedRom } from "@/stores/roms";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: DetailedRom;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const romsStore = storeRoms();

const visible = computed(
  () => props.rom.sibling_roms.length > 0 && props.rom.rom_user != null,
);

const isMain = computed(() => props.rom.rom_user?.is_main_sibling === true);

const tooltip = computed(() =>
  isMain.value ? t("rom.default-version") : t("rom.set-as-default-version"),
);

async function toggle() {
  const ru = props.rom.rom_user;
  if (!ru) return;

  const before = ru.is_main_sibling;
  const next = !before;
  const data: Partial<RomUserData> = { is_main_sibling: next };

  ru.is_main_sibling = next;
  romsStore.update(props.rom);

  try {
    await romApi.updateUserRomProps({ romId: props.rom.id, data });
  } catch {
    ru.is_main_sibling = before;
    romsStore.update(props.rom);
    snackbar.error(t("rom.update-default-failed"), {
      icon: "mdi-alert-circle-outline",
    });
  }
}
</script>

<template>
  <RBtn
    v-if="visible"
    variant="outlined"
    size="small"
    density="compact"
    icon
    :aria-pressed="isMain"
    :aria-label="tooltip"
    :tooltip="tooltip"
    tooltip-location="top"
    class="main-sibling-toggle"
    :class="{ 'main-sibling-toggle--on': isMain }"
    @click="toggle"
  >
    <RIcon
      :icon="isMain ? 'mdi-bookmark-box' : 'mdi-bookmark-box-outline'"
      size="18"
    />
  </RBtn>
</template>

<style scoped>
.main-sibling-toggle--on {
  color: var(--r-color-brand-accent) !important;
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-accent) 50%,
    transparent
  ) !important;
}
</style>
