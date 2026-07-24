<script setup lang="ts">
// TextViewer (v2) — renders a plain-text (.txt) or HTML (.html/.htm) document
// with the same v2 chrome as MarkdownViewer/PdfViewer. Used for manuals and
// walkthroughs. Plain text is fetched and shown in a <pre> (so reading
// progress can track its scroll); HTML is shown in a sandboxed iframe (the
// backend also serves it under a sandboxing CSP, so this is defense in depth).
import {
  RBtn,
  REmptyState,
  RIcon,
  RProgressLinear,
  RSpinner,
  RTooltip,
} from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useReadingProgress } from "@/v2/composables/useReadingProgress";

const props = defineProps<{
  url: string;
  /** ROM id + file id enable per-user reading-progress tracking (text only). */
  romId?: number;
  fileId?: number;
  /** Show a danger-tinted delete button at the end of the toolbar. */
  deletable?: boolean;
}>();

const emit = defineEmits<{ delete: [] }>();

const { t } = useI18n();

const isHtml = computed(() => /\.html?(\?|$)/i.test(props.url));

const fileName = computed(() => {
  const path = props.url.split("?")[0];
  const last = path.substring(path.lastIndexOf("/") + 1);
  try {
    return decodeURIComponent(last) || "document.txt";
  } catch {
    return last || "document.txt";
  }
});

const content = ref("");
const loading = ref(false);
const failed = ref(false);
const scrollEl = ref<HTMLElement | null>(null);

const romIdRef = computed(() => props.romId ?? 0);
const fileIdRef = computed(() =>
  props.romId != null && props.fileId != null ? props.fileId : null,
);
const { progress, restore, onScroll } = useReadingProgress(
  romIdRef,
  fileIdRef,
  scrollEl,
);

async function load() {
  if (isHtml.value) return; // iframe loads itself
  loading.value = true;
  failed.value = false;
  try {
    const res = await fetch(props.url, { credentials: "include" });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    content.value = await res.text();
    // Restore scroll after the <pre> has painted its content.
    requestAnimationFrame(() => void restore());
  } catch (err) {
    console.error("Failed to load text document", err);
    failed.value = true;
  } finally {
    loading.value = false;
  }
}

watch(() => props.url, load, { immediate: true });
</script>

<template>
  <div class="r-v2-txtv">
    <div class="r-v2-txtv__toolbar">
      <span class="r-v2-txtv__name">{{ fileName }}</span>

      <span class="r-v2-txtv__spacer" />

      <RTooltip :text="t('common.download')">
        <template #activator="{ props: activator }">
          <a
            v-bind="activator"
            :href="url"
            :download="fileName"
            class="r-v2-txtv__btn"
          >
            <RIcon icon="mdi-download" size="18" />
          </a>
        </template>
      </RTooltip>

      <RTooltip v-if="deletable" :text="t('common.delete')">
        <template #activator="{ props: activator }">
          <button
            v-bind="activator"
            type="button"
            class="r-v2-txtv__btn r-v2-txtv__btn--danger"
            @click="emit('delete')"
          >
            <RIcon icon="mdi-delete-outline" size="18" />
          </button>
        </template>
      </RTooltip>
    </div>

    <RProgressLinear
      v-if="fileIdRef != null && !isHtml"
      :model-value="progress * 100"
      height="2"
      class="r-v2-txtv__progress"
    />

    <div class="r-v2-txtv__viewer">
      <iframe
        v-if="isHtml"
        :src="url"
        sandbox=""
        referrerpolicy="no-referrer"
        class="r-v2-txtv__frame"
        :title="fileName"
      />
      <template v-else>
        <div v-if="loading" class="r-v2-txtv__center">
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
        <div v-else ref="scrollEl" class="r-v2-txtv__scroll" @scroll="onScroll">
          <pre class="r-v2-txtv__pre">{{ content }}</pre>
        </div>
      </template>
    </div>
  </div>
</template>

<style scoped>
.r-v2-txtv {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.r-v2-txtv__toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 10px;
}
.r-v2-txtv__name {
  font-size: 12px;
  color: var(--r-color-fg-muted);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-v2-txtv__spacer {
  flex: 1;
}
.r-v2-txtv__btn {
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
.r-v2-txtv__btn:hover {
  background: var(--r-color-surface-hover);
  color: var(--r-color-fg);
}
.r-v2-txtv__btn--danger {
  color: var(--r-color-danger);
}
.r-v2-txtv__btn--danger:hover {
  background: color-mix(in srgb, var(--r-color-danger) 14%, transparent);
  color: var(--r-color-danger);
}
.r-v2-txtv__progress {
  flex-shrink: 0;
}
.r-v2-txtv__viewer {
  flex: 1;
  min-height: 0;
  overflow: hidden;
  display: flex;
}
.r-v2-txtv__scroll {
  flex: 1;
  min-height: 0;
  overflow: auto;
}
.r-v2-txtv__frame {
  flex: 1;
  border: 0;
  width: 100%;
  height: 100%;
  background: var(--r-color-bg);
}
.r-v2-txtv__pre {
  margin: 0;
  padding: 16px;
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--r-font-mono, ui-monospace, monospace);
  font-size: 13px;
  line-height: 1.6;
  color: var(--r-color-fg);
}
.r-v2-txtv__center {
  display: flex;
  align-items: center;
  justify-content: center;
  height: 100%;
  width: 100%;
}
</style>
