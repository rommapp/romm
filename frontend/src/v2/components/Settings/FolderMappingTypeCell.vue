<script setup lang="ts">
// FolderMappingTypeCell — editable Type cell (alias / variant) for the
// folder mappings table.
//
// Same activator strategy as FolderMappingPlatformCell: plain
// `<button>` element bound to RMenu's activator slot props. This is
// the proven combo from `GameActionBtn.vue` — wrapping VMenu's
// slot-injected function ref through RBtn / VBtn breaks down in
// nested scoped-slot contexts (RTable's `cell.type` slot), so we
// attach the ref to a real DOM element directly.
//
// Editability matches v1: any row that already has a slug (whether
// alias, variant, or auto-detected) can be retyped. Auto rows can be
// converted to an explicit alias/variant by clicking the picker —
// `setType()` in FolderMappingsSection handles the auto → explicit
// transition by creating the matching binding. Unmapped rows
// (slug === undefined) stay non-editable here; the user picks a
// platform first via FolderMappingPlatformCell, which lands the row
// as `alias` by default.
import { RBtn, RMenu, RMenuItem, RMenuPanel, RTag, RIcon } from "@v2/lib";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

type RowType = "alias" | "variant" | "auto" | null;

interface Row {
  fsSlug: string;
  slug?: string;
  displayName?: string;
  type: RowType;
}

interface Props {
  row: Row;
  canEdit: boolean;
}
const props = defineProps<Props>();

defineEmits<{
  (e: "select", type: "alias" | "variant"): void;
}>();

const { t } = useI18n();

type RTagTone =
  | "neutral"
  | "brand"
  | "accent"
  | "success"
  | "danger"
  | "warning"
  | "info";

// Vuetify recognises `primary`, `accent`, `success`, etc. via the v2
// theme registration in `theme/vuetify.ts` — that's the colour the
// RBtn activator paints with. `brand` (an RTag tone alias for the
// brand-primary token) doesn't resolve in Vuetify's palette, which
// is why the alias chip stays uncoloured if you pass it to `:color`.
const btnColor = computed<"primary" | "accent" | "success">(() => {
  if (props.row.type === "alias") return "primary";
  if (props.row.type === "variant") return "accent";
  return "success"; // auto
});

// RTag is only rendered in the readonly fallback (non-editable +
// type set). Use the RTag-native tone vocabulary which paints from
// the same tokens but goes through the tag's CSS rules.
const tagTone = computed<RTagTone>(() => {
  if (props.row.type === "alias") return "brand";
  if (props.row.type === "variant") return "accent";
  return "success"; // auto
});

const label = computed(() => {
  if (props.row.type === "alias") return t("settings.folder-alias");
  if (props.row.type === "variant") return t("settings.platform-variant");
  return t("settings.auto-detected");
});

const isEditable = computed(() => props.canEdit && !!props.row.slug);

const open = ref(false);
</script>

<template>
  <RMenu v-if="isEditable" v-model="open" location="bottom">
    <template #activator="{ props: activatorProps }">
      <RBtn
        v-bind="activatorProps"
        type="button"
        class="r-v2-fmtc__btn"
        size="small"
        :color="btnColor"
        :aria-label="t('settings.mapping-types')"
      >
        <span class="r-v2-fmtc__label">{{ label }}</span>
        <RIcon icon="mdi-chevron-down" size="14" class="r-v2-fmtc__chevron" />
      </RBtn>
    </template>
    <RMenuPanel width="200px">
      <RMenuItem
        :label="t('settings.folder-alias')"
        icon="mdi-label-variant"
        @click="$emit('select', 'alias')"
      />
      <RMenuItem
        :label="t('settings.platform-variant')"
        icon="mdi-source-branch"
        @click="$emit('select', 'variant')"
      />
    </RMenuPanel>
  </RMenu>
  <RTag v-else-if="row.type" :tone="tagTone" :text="label" size="x-small" />
</template>

<style scoped>
/* Plain-button activator styled to read as a clickable tag pill. */
.r-v2-fmtc__btn {
  appearance: none;
  background: transparent;
  border: 0;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  cursor: pointer;
  font: inherit;
  border-radius: var(--r-radius-sm);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-fmtc__btn:hover,
.r-v2-fmtc__btn:focus-visible {
  background: var(--r-color-surface-hover);
}
.r-v2-fmtc__label {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
