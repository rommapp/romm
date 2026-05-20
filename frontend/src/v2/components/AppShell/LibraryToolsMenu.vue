<script setup lang="ts">
// LibraryToolsMenu — utility icon-button in the AppNav right cluster
// that opens a dropdown with Scan / Upload / Patcher. Replaces the
// previous "Library Tools" primary nav tab + sub-pill pattern.
//
// Rationale: the three tools are administrative actions, not content
// destinations. Putting them in the right cluster (alongside Classic
// UI and the user menu) frees the primary navigation pill for the
// four content destinations (Home / Platforms / Collections / Search)
// and keeps the tools discoverable without cluttering the nav.
//
// Active styling: when the user is on /scan, /upload, or /patcher, the
// icon button picks up a brand-tinted background so the chrome still
// communicates "you are inside the tools section". The chevron icon
// rotates to mirror the open state of the dropdown.
import { RBtn, RIcon, RMenu, RMenuItem } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { ROUTES } from "@/plugins/router";
import storeAuth from "@/stores/auth";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();
const route = useRoute();
const { scopes } = storeToRefs(storeAuth());

const open = ref(false);

const canScan = computed(() => scopes.value.includes("platforms.write"));
const canUpload = computed(() => scopes.value.includes("roms.write"));
// Patcher is always reachable (matches v1) — pure client-side worker.

const inToolsSection = computed(
  () =>
    route.path === "/scan" ||
    route.path === "/upload" ||
    route.path === "/patcher",
);
</script>

<template>
  <RMenu v-model="open" location="bottom end" :offset="8" width="220px">
    <template #activator="{ props: menuProps }">
      <!-- RBtn directly receives the menu activator props. We
           intentionally do NOT nest an RTooltip activator on top of
           this — both RMenu and RTooltip register a template `ref`
           callback on their activator slot, and spreading both onto
           the same RBtn would let one overwrite the other's ref,
           leaving the menu without a positioning anchor (it would
           then fall back to the viewport top-left corner). The icon
           + chevron + aria-label communicate the affordance without
           a tooltip. -->
      <RBtn
        v-bind="menuProps"
        size="small"
        variant="text"
        :title="t('library-tools.title', 'Library tools')"
        class="r-v2-lt-menu"
        :class="{
          'r-v2-lt-menu--active': inToolsSection,
        }"
        :aria-label="t('library-tools.title', 'Library tools')"
        aria-haspopup="menu"
        :aria-expanded="open"
      >
        <RIcon icon="mdi-tools" size="18" />
        <span class="r-v2-lt-menu__label">
          {{ t("library-tools.title", "Library tools") }}
        </span>
        <RIcon icon="mdi-chevron-down" size="14" class="r-chevron-toggle" />
      </RBtn>
    </template>

    <!-- Section header — same eyebrow styling as UserMenu groups so
         the two dropdowns read as siblings. -->
    <div class="r-v2-lt-menu__header">
      {{ t("library-tools.title", "Library tools") }}
    </div>

    <RMenuItem
      :to="{ name: ROUTES.SCAN }"
      icon="mdi-magnify-scan"
      :label="t('scan.scan')"
      :disabled="!canScan"
      @click="open = false"
    />
    <RMenuItem
      :to="{ name: ROUTES.UPLOAD }"
      icon="mdi-cloud-upload-outline"
      :label="t('common.upload-roms', 'Upload ROMs')"
      :disabled="!canUpload"
      @click="open = false"
    />
    <RMenuItem
      :to="{ name: ROUTES.PATCHER }"
      icon="mdi-file-cog-outline"
      :label="t('common.patcher')"
      @click="open = false"
    />
  </RMenu>
</template>

<style scoped>
/* Ghost-pill look, same vocabulary as the Classic UI button so the
   right cluster reads as a coherent strip. Becomes brand-tinted when
   the user is inside the tools section (active state). */
.r-v2-lt-menu {
  background: var(--r-color-surface) !important;
  border: 1px solid var(--r-color-border-strong) !important;
  color: var(--r-color-fg-secondary) !important;
  display: inline-flex;
  align-items: center;
  gap: 2px !important;
  padding: 0 8px !important;
  min-width: 0 !important;
}
.r-v2-lt-menu:hover {
  background: var(--r-color-surface-hover) !important;
  color: var(--r-color-fg) !important;
}
/* Active state — neutral surface emphasis (no brand colour). The
   button reads as "you're in this section" via a slightly stronger
   surface bg + full-strength fg, without screaming for attention
   the way a brand-tinted pill would. */
.r-v2-lt-menu--active,
.r-v2-lt-menu--active:hover {
  background: var(--r-color-surface-hover) !important;
  border-color: var(--r-color-border-strong) !important;
  color: var(--r-color-fg) !important;
}

.r-v2-lt-menu__header {
  padding: 10px 14px 4px;
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  letter-spacing: 0.04em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
}
.r-v2-lt-menu__label {
  margin: 8px;
}
</style>
