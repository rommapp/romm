<script setup lang="ts">
// PdfViewer (v2) — wraps `vue3-pdf-app` with v2 chrome:
//
//   * Single bg-elevated panel hosts toolbar + canvas. The toolbar
//     shares the same surface as the PDF area (no internal divider /
//     bottom border) so the pane reads as one continuous panel.
//   * Plain <button> + RIcon + RTooltip per toolbar action — vue3-pdf-app
//     wires controls by `id`, so raw buttons keep that contract while
//     the v2 visual is owned by our scoped CSS.
import { RIcon, RTooltip } from "@v2/lib";
import { computed } from "vue";
import VuePdfApp from "vue3-pdf-app";
import { useI18n } from "vue-i18n";
import { useBreakpoint } from "@/v2/composables/useBreakpoint";
import { useThemeMode } from "@/v2/composables/useThemeMode";

defineProps<{
  pdfUrl: string;
  /** Show a danger-tinted delete button at the end of the toolbar. */
  deletable?: boolean;
  /** Show a re-download button (next to Download) when a scraped source
   *  URL exists for this manual. */
  redownloadable?: boolean;
  /** Drive the re-download button's loading/disabled state. */
  redownloading?: boolean;
}>();

const emit = defineEmits<{
  delete: [];
  redownload: [];
}>();

const { t } = useI18n();
const { xs } = useBreakpoint();
const { isLight } = useThemeMode();
const pdfTheme = computed<"light" | "dark">(() =>
  isLight.value ? "light" : "dark",
);

// IDs the library reaches for to wire up the custom toolbar — must
// match the field names of the `id-config` prop below.
const ids = {
  sidebarToggle: "sidebarToggleId",
  pageNumber: "pageNumberId",
  numPages: "numPagesId",
  zoomIn: "zoomInId",
  zoomOut: "zoomOutId",
  firstPage: "firstPageId",
  previousPage: "previousPageId",
  nextPage: "nextPageId",
  lastPage: "lastPageId",
  download: "downloadId",
};
</script>

<template>
  <div class="r-v2-pdfv">
    <div class="r-v2-pdfv__toolbar">
      <RTooltip :text="t('rom.pdf-toggle-sidebar')">
        <template #activator="{ props: activator }">
          <button
            :id="ids.sidebarToggle"
            v-bind="activator"
            type="button"
            class="r-v2-pdfv__btn"
          >
            <RIcon icon="mdi-menu" size="18" />
          </button>
        </template>
      </RTooltip>

      <span class="r-v2-pdfv__sep" aria-hidden="true" />

      <RTooltip :text="t('common.first-page')">
        <template #activator="{ props: activator }">
          <button
            :id="ids.firstPage"
            v-bind="activator"
            type="button"
            class="r-v2-pdfv__btn"
          >
            <RIcon icon="mdi-page-first" size="18" />
          </button>
        </template>
      </RTooltip>

      <RTooltip v-if="!xs" :text="t('common.previous-page')">
        <template #activator="{ props: activator }">
          <button
            :id="ids.previousPage"
            v-bind="activator"
            type="button"
            class="r-v2-pdfv__btn"
          >
            <RIcon icon="mdi-chevron-left" size="18" />
          </button>
        </template>
      </RTooltip>

      <input
        :id="ids.pageNumber"
        type="number"
        class="r-v2-pdfv__page-input"
        :aria-label="t('common.page')"
      />
      <span :id="ids.numPages" class="r-v2-pdfv__page-total" />

      <RTooltip v-if="!xs" :text="t('common.next-page')">
        <template #activator="{ props: activator }">
          <button
            :id="ids.nextPage"
            v-bind="activator"
            type="button"
            class="r-v2-pdfv__btn"
          >
            <RIcon icon="mdi-chevron-right" size="18" />
          </button>
        </template>
      </RTooltip>

      <RTooltip :text="t('common.last-page')">
        <template #activator="{ props: activator }">
          <button
            :id="ids.lastPage"
            v-bind="activator"
            type="button"
            class="r-v2-pdfv__btn"
          >
            <RIcon icon="mdi-page-last" size="18" />
          </button>
        </template>
      </RTooltip>

      <span class="r-v2-pdfv__spacer" />

      <RTooltip :text="t('common.zoom-out')">
        <template #activator="{ props: activator }">
          <button
            :id="ids.zoomOut"
            v-bind="activator"
            type="button"
            class="r-v2-pdfv__btn"
          >
            <RIcon icon="mdi-magnify-minus-outline" size="18" />
          </button>
        </template>
      </RTooltip>

      <RTooltip :text="t('common.zoom-in')">
        <template #activator="{ props: activator }">
          <button
            :id="ids.zoomIn"
            v-bind="activator"
            type="button"
            class="r-v2-pdfv__btn"
          >
            <RIcon icon="mdi-magnify-plus-outline" size="18" />
          </button>
        </template>
      </RTooltip>

      <span class="r-v2-pdfv__spacer" />

      <RTooltip :text="t('common.download')">
        <template #activator="{ props: activator }">
          <button
            :id="ids.download"
            v-bind="activator"
            type="button"
            class="r-v2-pdfv__btn"
          >
            <RIcon icon="mdi-download" size="18" />
          </button>
        </template>
      </RTooltip>

      <RTooltip v-if="redownloadable" :text="t('rom.redownload')">
        <template #activator="{ props: activator }">
          <button
            v-bind="activator"
            type="button"
            class="r-v2-pdfv__btn"
            :class="{ 'r-v2-pdfv__btn--loading': redownloading }"
            :disabled="redownloading"
            @click="emit('redownload')"
          >
            <RIcon icon="mdi-cloud-download-outline" size="18" />
          </button>
        </template>
      </RTooltip>

      <RTooltip v-if="deletable" :text="t('common.delete')">
        <template #activator="{ props: activator }">
          <button
            v-bind="activator"
            type="button"
            class="r-v2-pdfv__btn r-v2-pdfv__btn--danger"
            @click="emit('delete')"
          >
            <RIcon icon="mdi-delete-outline" size="18" />
          </button>
        </template>
      </RTooltip>
    </div>

    <div class="r-v2-pdfv__viewer">
      <VuePdfApp
        :id-config="ids"
        :config="{ toolbar: false }"
        :theme="pdfTheme"
        :pdf="pdfUrl"
        class="r-v2-pdfv__app"
      />
    </div>
  </div>
</template>

<style scoped>
.r-v2-pdfv {
  display: flex;
  flex-direction: column;
  /* Fills the parent container exactly — height comes from the chain
     `.r-v2-det__panel → .r-v2-media → .r-v2-media__panel →
     .r-v2-manual__viewer`, all flex-sized. The viewer never overflows
     so the only visible scroll is the PDF's own internal one. */
  height: 100%;
}

/* Toolbar inherits the parent's bg-elevated — no separate background
   or divider so the surface reads as one continuous panel. */
.r-v2-pdfv__toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 10px;
}
.r-v2-pdfv__sep {
  width: 1px;
  height: 18px;
  background: var(--r-color-border);
  margin: 0 6px;
}
.r-v2-pdfv__spacer {
  flex: 1;
}

.r-v2-pdfv__btn {
  appearance: none;
  background: transparent;
  border: 0;
  cursor: pointer;
  padding: 6px;
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg-secondary);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-family: inherit;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-pdfv__btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
/* Danger variant — Delete sits at the end of the toolbar, so it takes
   a danger-tinted foreground + hover so the destructive action reads
   different from the navigation/zoom siblings. */
.r-v2-pdfv__btn--danger {
  color: var(--r-color-danger);
}
.r-v2-pdfv__btn--danger:hover {
  background: color-mix(in srgb, var(--r-color-danger) 14%, transparent);
  color: var(--r-color-danger);
}
.r-v2-pdfv__btn--loading {
  opacity: 0.6;
  cursor: not-allowed;
}
.r-v2-pdfv__btn--loading:hover {
  background: transparent;
  color: var(--r-color-fg-secondary);
}

.r-v2-pdfv__page-input {
  width: 48px;
  text-align: center;
  background: transparent;
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-sm);
  color: var(--r-color-fg);
  font-family: inherit;
  font-size: 12px;
  padding: 2px 4px;
  margin-left: 6px;
  -moz-appearance: textfield;
  appearance: textfield;
  transition: border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-pdfv__page-input::-webkit-outer-spin-button,
.r-v2-pdfv__page-input::-webkit-inner-spin-button {
  -webkit-appearance: none;
  margin: 0;
}
.r-v2-pdfv__page-input:focus {
  outline: none;
  border-color: var(--r-color-brand-primary);
}
.r-v2-pdfv__page-total {
  font-size: 12px;
  color: var(--r-color-fg-muted);
  margin: 0 6px 0 4px;
  font-variant-numeric: tabular-nums;
}

.r-v2-pdfv__viewer {
  /* Fills remaining height after the toolbar via flex. min-height: 0
     lets the canvas shrink below its intrinsic content size (PDF.js
     would otherwise force the wrap to grow indefinitely). */
  flex: 1;
  min-height: 0;
}
.r-v2-pdfv__app {
  height: 100%;
}

/* vue3-pdf-app paints its own canvas chrome via this CSS variable.
   Override with v2 tokens so the canvas blends with the surrounding
   bg-elevated container — no visible seam between toolbar and canvas. */
.r-v2-pdfv__viewer :deep(.pdf-app.dark),
.r-v2-pdfv__viewer :deep(.pdf-app.light) {
  --pdf-app-background-color: var(--r-color-bg-elevated) !important;
}
</style>
