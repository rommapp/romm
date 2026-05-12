<script setup lang="ts">
// FolderMappingPlatformCell — editable Platform cell for the folder
// mappings table.
//
// Activator: a plain `<button>` element bound directly via `v-bind` to
// the slot scope's activator props. Same combination GameActionBtn
// uses in production v2 code (RMenu + activator slot + plain button).
// VMenu's slot-injected function ref has to attach to a real DOM
// element, and Vue 3 doesn't forward such refs cleanly through
// wrapper components (RBtn → VBtn) when the activator is rendered
// inside a deeply scoped parent slot (RTable's `cell.platform` slot).
//
// The dropdown content is the shared `PlatformPickerMenu`, so every
// surface that picks a platform — this one and MissingGames — uses
// the same searchable, icon-decorated menu (same scrollbar, same
// panel paint, same item layout).
import { RIcon, RMenu, RMenuItem } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import type { Platform } from "@/stores/platforms";
import CachedPlatformIcon from "@/v2/components/shared/CachedPlatformIcon.vue";
import PlatformPickerMenu, {
  type PlatformOption,
} from "@/v2/components/shared/PlatformPickerMenu.vue";

type RowType = "alias" | "variant" | "auto" | null;

interface Row {
  fsSlug: string;
  slug?: string;
  displayName?: string;
  type: RowType;
}

interface Props {
  row: Row;
  supportedPlatforms: Platform[];
  canEdit: boolean;
}
const props = defineProps<Props>();

const emit = defineEmits<{
  /** New platform slug (or undefined to clear the mapping). */
  (e: "select", slug: string | undefined): void;
}>();

const { t } = useI18n();

const open = ref(false);

// Adapt the section's `Platform[]` to the picker's generic option
// shape — id stays absent (we key by slug here).
const platformOptions = computed<PlatformOption[]>(() =>
  props.supportedPlatforms.map((p) => ({
    slug: p.slug,
    name: p.display_name,
  })),
);

function pick(slug: string | undefined) {
  emit("select", slug);
  open.value = false;
}
</script>

<template>
  <RMenu
    v-if="canEdit"
    v-model="open"
    location="bottom start"
    :close-on-content-click="false"
  >
    <template #activator="{ props: activatorProps }">
      <button
        v-bind="activatorProps"
        type="button"
        class="r-v2-fmpc__btn"
        :aria-label="t('settings.platforms')"
      >
        <CachedPlatformIcon
          v-if="row.slug"
          :slug="row.slug"
          :size="20"
          class="r-v2-fmpc__icon"
        />
        <span v-if="row.slug" class="r-v2-fmpc__name">
          {{ row.displayName }}
        </span>
        <span v-else class="r-v2-fmpc__placeholder">—</span>
        <RIcon icon="mdi-chevron-down" size="14" class="r-v2-fmpc__chevron" />
      </button>
    </template>
    <PlatformPickerMenu
      :platforms="platformOptions"
      :search-placeholder="t('common.search')"
      @select="(p) => pick(p.slug)"
    >
      <template #footer="{ query }">
        <RMenuItem
          v-if="!query && row.slug && row.type !== 'auto'"
          icon="mdi-delete"
          variant="danger"
          :label="t('common.delete')"
          @click="pick(undefined)"
        />
      </template>
    </PlatformPickerMenu>
  </RMenu>
  <span v-else class="r-v2-fmpc__readonly">
    <CachedPlatformIcon
      v-if="row.slug"
      :slug="row.slug"
      :size="20"
      class="r-v2-fmpc__icon"
    />
    <span v-if="row.slug" class="r-v2-fmpc__name">{{ row.displayName }}</span>
    <span v-else class="r-v2-fmpc__placeholder">—</span>
  </span>
</template>

<style scoped>
/* Plain-button activator styled to read as a v2 text button. */
.r-v2-fmpc__btn {
  appearance: none;
  background: transparent;
  border: 0;
  padding: 4px 8px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  font: inherit;
  font-size: 13px;
  font-weight: var(--r-font-weight-regular);
  color: var(--r-color-fg);
  border-radius: var(--r-radius-sm);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-fmpc__btn:hover,
.r-v2-fmpc__btn:focus-visible {
  background: var(--r-color-surface-hover);
}
.r-v2-fmpc__icon {
  flex-shrink: 0;
}
.r-v2-fmpc__name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-v2-fmpc__chevron {
  color: var(--r-color-fg-muted);
}
.r-v2-fmpc__readonly {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--r-color-fg);
}
.r-v2-fmpc__placeholder {
  color: var(--r-color-fg-faint);
}
</style>
