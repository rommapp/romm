<script setup lang="ts">
// VersionSwitcher — RBtn + RMenu pair that lets the user navigate
// between sibling ROMs of the same game (different region / revision /
// language). Renders nothing when the rom has no siblings.
//
// Layout follows the v1 FileInfo row: the switcher pill sits next to
// the MainSiblingToggle so "see other versions" and "make this one the
// default" read as a single control group. The active row in the menu
// is the rom currently in view (radio-like), so the user can confirm
// which file they're on without scanning filenames.
import { RBtn, RIcon, RMenu, RMenuItem } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import type { DetailedRom } from "@/stores/roms";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  rom: DetailedRom;
}>();

const { t } = useI18n();

const visible = computed(() => props.rom.sibling_roms.length > 0);

// `main` flags the user-marked default version. Read off `rom_user`
// for this rom and off the per-sibling `is_main_sibling` field for the
// rest (resolved by the backend against the request user's RomUser),
// so the badge surfaces consistently regardless of which sibling the
// user is currently viewing.
const versions = computed(() => [
  {
    id: props.rom.id,
    label: props.rom.fs_name_no_ext,
    current: true,
    main: props.rom.rom_user?.is_main_sibling === true,
  },
  ...props.rom.sibling_roms.map((s) => ({
    id: s.id,
    label: s.fs_name_no_ext,
    current: false,
    main: s.is_main_sibling === true,
  })),
]);

const currentLabel = computed(() => props.rom.fs_name_no_ext);
const mainTooltip = computed(() => t("rom.default-version"));
</script>

<template>
  <RMenu v-if="visible" location="bottom start" :offset="6">
    <template #activator="{ props: activatorProps }">
      <RBtn
        v-bind="activatorProps"
        variant="outlined"
        size="small"
        density="compact"
        class="version-switcher__btn"
        :aria-label="t('rom.switch-version')"
      >
        <RIcon icon="mdi-card-multiple-outline" size="16" />
        <span class="version-switcher__label">{{ currentLabel }}</span>
        <RIcon icon="mdi-menu-down" size="16" />
      </RBtn>
    </template>

    <RMenuItem
      v-for="v in versions"
      :key="v.id"
      :to="`/rom/${v.id}`"
      :variant="v.current ? 'active' : 'default'"
      :icon="v.current ? 'mdi-check' : undefined"
      :label="v.label"
    >
      <template v-if="v.main" #append>
        <RIcon
          icon="mdi-bookmark-box"
          size="14"
          class="version-switcher__main"
          :aria-label="mainTooltip"
        />
      </template>
    </RMenuItem>
  </RMenu>
</template>

<style scoped>
.version-switcher__btn {
  /* Caps the activator pill so very long filenames truncate instead of
     stretching the row. The menu items show the full label. */
  max-width: 320px;
}
.version-switcher__label {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  min-width: 0;
  flex: 1;
  text-align: left;
}

.version-switcher__main {
  color: var(--r-color-brand-accent);
}
</style>
