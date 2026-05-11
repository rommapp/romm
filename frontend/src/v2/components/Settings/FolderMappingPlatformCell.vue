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
// The picker is filterable via RMenuPanel's `searchable` prop, which
// renders a built-in sticky header. `closeOnContentClick=false`
// keeps the menu open while typing; item selection closes it
// explicitly via `pick()`.
import { RIcon, RMenu, RMenuItem, RMenuPanel } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import CachedPlatformIcon from "@/v2/components/shared/CachedPlatformIcon.vue";
import type { Platform } from "@/stores/platforms";

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
const query = ref("");

// Reset the search every time the menu closes so the next open
// starts fresh — typical picker UX.
watch(open, (v) => {
  if (!v) query.value = "";
});

const filteredPlatforms = computed(() => {
  const q = query.value.trim().toLowerCase();
  if (!q) return props.supportedPlatforms;
  return props.supportedPlatforms.filter((p) => {
    const name = (p.display_name || "").toLowerCase();
    const slug = (p.slug || "").toLowerCase();
    return name.includes(q) || slug.includes(q);
  });
});

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
    <RMenuPanel
      width="280px"
      max-height="360px"
      searchable
      v-model:search="query"
      :search-placeholder="t('common.search')"
    >
      <RMenuItem
        v-for="platform in filteredPlatforms"
        :key="platform.slug"
        :label="platform.display_name"
        @click="pick(platform.slug)"
      >
        <template #icon>
          <CachedPlatformIcon
            :slug="platform.slug"
            :name="platform.display_name"
            :size="18"
          />
        </template>
      </RMenuItem>
      <div
        v-if="filteredPlatforms.length === 0"
        class="r-v2-fmpc__empty"
      >
        {{ t("common.no-results") }}
      </div>
      <RMenuItem
        v-if="!query && row.slug && row.type !== 'auto'"
        icon="mdi-delete"
        variant="danger"
        :label="t('common.delete')"
        @click="pick(undefined)"
      />
    </RMenuPanel>
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
/* Plain-button activator styled to read as a v2 text button. Keeps
   parity with the previous RBtn-based look (gap, color, hover). */
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
.r-v2-fmpc__empty {
  padding: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
</style>
