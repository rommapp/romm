<script setup lang="ts">
// MarkdownViewer (v2) — renders a Markdown (.md) manual with the same v2
// chrome as PdfViewer. Manuals can be PDF or Markdown; MediaTab picks the
// viewer by extension. The file is fetched as text and handed to MdPreview
// (md-editor-v3), the same renderer used by NotesTab.
import { RBtn, REmptyState, RIcon, RSpinner, RTooltip } from "@v2/lib";
import { MdPreview } from "md-editor-v3";
import "md-editor-v3/lib/style.css";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useThemeMode } from "@/v2/composables/useThemeMode";

const props = defineProps<{
  url: string;
  /** Show a danger-tinted delete button at the end of the toolbar. */
  deletable?: boolean;
  /** Show a re-download button when a scraped source URL exists. */
  redownloadable?: boolean;
  /** Drive the re-download button's loading/disabled state. */
  redownloading?: boolean;
}>();

const emit = defineEmits<{
  delete: [];
  redownload: [];
}>();

const { t } = useI18n();
const { isLight } = useThemeMode();
const mdTheme = computed<"light" | "dark">(() =>
  isLight.value ? "light" : "dark",
);

// Filename for the download button — last path segment without the cache-bust
// query, decoded back to its human form (e.g. `README.md`).
const fileName = computed(() => {
  const path = props.url.split("?")[0];
  const last = path.substring(path.lastIndexOf("/") + 1);
  try {
    return decodeURIComponent(last) || "manual.md";
  } catch {
    return last || "manual.md";
  }
});

const content = ref("");
const loading = ref(false);
const failed = ref(false);

async function load() {
  loading.value = true;
  failed.value = false;
  try {
    const res = await fetch(props.url, { credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    content.value = await res.text();
  } catch (err) {
    console.error("Failed to load markdown manual", err);
    failed.value = true;
  } finally {
    loading.value = false;
  }
}

watch(() => props.url, load, { immediate: true });
</script>

<template>
  <div class="r-v2-mdv">
    <div class="r-v2-mdv__toolbar">
      <span class="r-v2-mdv__name">{{ fileName }}</span>

      <span class="r-v2-mdv__spacer" />

      <RTooltip :text="t('common.download')">
        <template #activator="{ props: activator }">
          <a
            v-bind="activator"
            :href="url"
            :download="fileName"
            class="r-v2-mdv__btn"
          >
            <RIcon icon="mdi-download" size="18" />
          </a>
        </template>
      </RTooltip>

      <RTooltip v-if="redownloadable" :text="t('rom.redownload')">
        <template #activator="{ props: activator }">
          <button
            v-bind="activator"
            type="button"
            class="r-v2-mdv__btn"
            :class="{ 'r-v2-mdv__btn--loading': redownloading }"
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
            class="r-v2-mdv__btn r-v2-mdv__btn--danger"
            @click="emit('delete')"
          >
            <RIcon icon="mdi-delete-outline" size="18" />
          </button>
        </template>
      </RTooltip>
    </div>

    <div class="r-v2-mdv__viewer">
      <div v-if="loading" class="r-v2-mdv__center">
        <RSpinner :size="28" />
      </div>
      <REmptyState
        v-else-if="failed"
        icon="mdi-file-alert-outline"
        :title="t('rom.manual-load-failed')"
      >
        <template #actions>
          <RBtn variant="outlined" size="small" @click="load">
            {{ t("common.try-again") }}
          </RBtn>
        </template>
      </REmptyState>
      <MdPreview
        v-else
        no-highlight
        no-katex
        no-mermaid
        :model-value="content"
        :theme="mdTheme"
        language="en-US"
        preview-theme="vuepress"
        code-theme="github"
        class="r-v2-mdv__preview"
      />
    </div>
  </div>
</template>

<style scoped>
.r-v2-mdv {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}

/* Toolbar inherits the parent's bg-elevated — no separate background or
   divider so the surface reads as one continuous panel (mirrors PdfViewer). */
.r-v2-mdv__toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 10px;
}
.r-v2-mdv__name {
  font-size: 12px;
  color: var(--r-color-fg-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-v2-mdv__spacer {
  flex: 1;
}

.r-v2-mdv__btn {
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
.r-v2-mdv__btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-mdv__btn--danger {
  color: var(--r-color-danger);
}
.r-v2-mdv__btn--danger:hover {
  background: color-mix(in srgb, var(--r-color-danger) 14%, transparent);
  color: var(--r-color-danger);
}
.r-v2-mdv__btn--loading {
  opacity: 0.6;
  cursor: not-allowed;
}
.r-v2-mdv__btn--loading:hover {
  background: transparent;
  color: var(--r-color-fg-secondary);
}

.r-v2-mdv__viewer {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.r-v2-mdv__center {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
}

/* MdPreview paints its own surface — blend it with the surrounding
   bg-elevated container so there's no visible seam under the toolbar. */
.r-v2-mdv__preview {
  background: transparent;
  padding: 0 16px 16px;
}
</style>
