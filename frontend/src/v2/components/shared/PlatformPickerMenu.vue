<script setup lang="ts">
// PlatformPickerMenu — shared dropdown body for any surface that
// needs to pick a platform. Renders an RMenuPanel with a sticky
// `searchable` header and a filterable list of platforms (each with
// its CachedPlatformIcon). Designed to be dropped inside an `RMenu`
// so the calling surface owns the activator + open/close state — the
// menu visual itself (panel paint, scrollbar, item layout) stays
// identical wherever it's used.
//
// Consumers (`FolderMappingPlatformCell`, `MissingGamesSection`,
// future Settings surfaces) wrap this in their own `RMenu` with
// `:close-on-content-click="false"` and handle the picked event +
// any closing logic.
//
// `#footer` slot lets each consumer drop in surface-specific
// terminal actions (e.g. "Delete mapping", "Clear filter") after
// the list. The slot scope exposes the current `query` so the
// footer can be hidden mid-search if that suits the UX.
import { RMenuItem, RMenuPanel } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import CachedPlatformIcon from "@/v2/components/shared/CachedPlatformIcon.vue";

export interface PlatformOption {
  /** Optional caller-defined id (e.g. numeric platform id). The
   *  picker treats this as opaque — emitted back to the parent so
   *  consumers can match against their own data shape. */
  id?: string | number;
  slug: string;
  name: string;
}

interface Props {
  platforms: PlatformOption[];
  searchPlaceholder?: string;
  /** v-model:query — current search string. Two-way bound so a
   *  parent can react to the query (e.g. hide a clear footer mid
   *  search). */
  query?: string;
  /** Width of the dropdown panel. */
  width?: string | number;
  /** Max height of the scrollable list. */
  maxHeight?: string | number;
}

const props = withDefaults(defineProps<Props>(), {
  searchPlaceholder: "",
  query: "",
  width: "280px",
  maxHeight: "360px",
});

const emit = defineEmits<{
  (e: "select", platform: PlatformOption): void;
  (e: "update:query", value: string): void;
}>();

defineSlots<{
  /** Trailing menu region — typically a destructive / reset action
   *  pinned below the list. Scope exposes the current `query` so
   *  the slot content can be conditional on search state. */
  footer?: (props: { query: string }) => unknown;
}>();

const { t } = useI18n();

// Mirror the prop so a consumer that doesn't bind v-model:query
// still gets a working internal search.
const localQuery = ref(props.query);
watch(
  () => props.query,
  (v) => {
    localQuery.value = v;
  },
);
function onQueryUpdate(v: string) {
  localQuery.value = v;
  emit("update:query", v);
}

const filtered = computed(() => {
  const q = localQuery.value.trim().toLowerCase();
  if (!q) return props.platforms;
  return props.platforms.filter(
    (p) => p.name.toLowerCase().includes(q) || p.slug.toLowerCase().includes(q),
  );
});
</script>

<template>
  <RMenuPanel
    :width="width"
    :max-height="maxHeight"
    searchable
    :search="localQuery"
    :search-placeholder="searchPlaceholder"
    @update:search="onQueryUpdate"
  >
    <RMenuItem
      v-for="platform in filtered"
      :key="platform.slug"
      :label="platform.name"
      @click="$emit('select', platform)"
    >
      <template #icon>
        <CachedPlatformIcon
          :slug="platform.slug"
          :name="platform.name"
          :size="18"
        />
      </template>
    </RMenuItem>
    <div v-if="filtered.length === 0" class="r-v2-platform-picker__empty">
      {{ t("common.no-results") }}
    </div>
    <slot name="footer" :query="localQuery" />
  </RMenuPanel>
</template>

<style scoped>
.r-v2-platform-picker__empty {
  padding: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
</style>
