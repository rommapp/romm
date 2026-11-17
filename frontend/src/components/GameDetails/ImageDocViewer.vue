<script setup lang="ts">
// The backend serves pages one at a time, so the archive never has to download.
import { computed, nextTick, ref, useTemplateRef, watch } from "vue";
import { useI18n } from "vue-i18n";
import ViewerZoomControls from "@/components/GameDetails/ViewerZoomControls.vue";
import { useFetchState } from "@/composables/useFetchState";
import { useReadingProgress } from "@/composables/useReadingProgress";
import { useViewerZoom } from "@/composables/useViewerZoom";
import {
  RBtn,
  REmptyState,
  RProgressLinear,
  RSpinner,
  RTextField,
} from "@/lib";
import romApi from "@/services/api/rom";
import { imageDocPageUrl } from "@/utils/romFiles";

const props = defineProps<{
  /** API path of the pages, from `imageDocPagesPath`. */
  pagesPath: string;
  /** Bumped when the archive changes, so cached pages are refetched. */
  version: string;
  downloadUrl: string;
  fileName: string;
  /** ROM id + file id persist the reading position; without them the progress
   *  bar still tracks the session's page. */
  romId?: number;
  fileId?: number | undefined;
  /** Show a danger-tinted delete button at the end of the toolbar. */
  deletable?: boolean;
  /** Show a re-download button when a scraped source URL exists. */
  redownloadable?: boolean;
  redownloading?: boolean;
}>();

const emit = defineEmits<{
  delete: [];
  redownload: [];
}>();

const { t } = useI18n();

const { fit, zoom, canZoomIn, canZoomOut, zoomIn, zoomOut, toggleFit } =
  useViewerZoom("ui.imageDocFit", "page");
const stageEl = useTemplateRef<HTMLElement>("stage");

const romIdRef = computed(() => props.romId ?? 0);
const fileIdRef = computed(() =>
  props.romId != null && props.fileId != null ? props.fileId : null,
);
const { progress, restore, setPage, suppressWhileRestoring } =
  useReadingProgress(romIdRef, fileIdRef);

const page = ref(1);
const pageInput = ref("1");
const imageLoading = ref(true);
const imageFailed = ref(false);

const {
  state: pageCount,
  isLoading: countLoading,
  error: countError,
  execute: loadCount,
} = useFetchState(
  async () => {
    const { data } = await romApi.getImageDocPageCount({
      pagesPath: props.pagesPath,
    });
    return data.count;
  },
  0,
  {
    immediate: false,
    onSuccess: (count) => void restorePosition(count),
    onError: (err) => console.error("Failed to load image doc pages", err),
  },
);
const countFailed = computed(() => countError.value !== undefined);

const pageSrc = computed(() =>
  imageDocPageUrl(props.pagesPath, page.value, props.version),
);

async function restorePosition(count: number) {
  if (count <= 0) return;
  // A page turned while the saved position is in flight wins over it.
  const pageBeforeRestore = page.value;
  const { lastPage } = await restore();
  if (
    page.value === pageBeforeRestore &&
    lastPage &&
    lastPage > 1 &&
    lastPage <= count
  ) {
    suppressWhileRestoring();
    page.value = lastPage;
  } else {
    setPage(page.value, count);
  }
}

watch(
  () => [props.pagesPath, props.version],
  () => {
    page.value = 1;
    void loadCount();
  },
  { immediate: true },
);

watch(page, (value) => {
  pageInput.value = String(value);
  imageLoading.value = true;
  imageFailed.value = false;
  stageEl.value?.scrollTo({ top: 0, left: 0 });
});

// Warm the cache with the next page so turning to it is instant.
function preloadNext() {
  if (page.value >= pageCount.value) return;
  const next = new Image();
  next.src = imageDocPageUrl(props.pagesPath, page.value + 1, props.version);
}

function onImageLoad() {
  imageLoading.value = false;
  preloadNext();
}

function onImageError() {
  imageLoading.value = false;
  imageFailed.value = true;
}

function goTo(target: number): boolean {
  const count = pageCount.value;
  if (count <= 0) return false;
  const clamped = Math.min(count, Math.max(1, Math.round(target)));
  if (clamped === page.value) return false;
  page.value = clamped;
  setPage(clamped, count);
  return true;
}

function commitPageInput() {
  const value = Number(pageInput.value);
  if (!Number.isFinite(value) || !goTo(value)) {
    pageInput.value = String(page.value);
  }
}

// Keeps the point at the middle of the stage in place across a rescale. The
// watcher runs before the DOM updates, so it still measures the old size.
watch(zoom, async () => {
  const el = stageEl.value;
  if (!el) return;
  const centre = {
    x: (el.scrollLeft + el.clientWidth / 2) / el.scrollWidth,
    y: (el.scrollTop + el.clientHeight / 2) / el.scrollHeight,
  };
  await nextTick();
  el.scrollLeft = centre.x * el.scrollWidth - el.clientWidth / 2;
  el.scrollTop = centre.y * el.scrollHeight - el.clientHeight / 2;
});

// Up/Down scroll a page taller than the stage; at its edge they are left
// unclaimed so spatial navigation can carry focus out.
function scrollStage(direction: 1 | -1): boolean {
  const el = stageEl.value;
  if (!el) return false;
  const atEdge =
    direction > 0
      ? el.scrollTop + el.clientHeight >= el.scrollHeight - 1
      : el.scrollTop <= 0;
  if (atEdge) return false;
  el.scrollBy({ top: direction * el.clientHeight * 0.8 });
  return true;
}

function onTurnKeydown(event: KeyboardEvent) {
  let handled = false;
  switch (event.key) {
    case "ArrowLeft":
    case "PageUp":
      handled = goTo(page.value - 1);
      break;
    case "ArrowRight":
    case "PageDown":
    case " ":
      handled = goTo(page.value + 1);
      break;
    case "Home":
      handled = goTo(1);
      break;
    case "End":
      handled = goTo(pageCount.value);
      break;
    case "ArrowDown":
      handled = scrollStage(1);
      break;
    case "ArrowUp":
      handled = scrollStage(-1);
      break;
    case "+":
    case "=":
      handled = zoomIn();
      break;
    case "-":
      handled = zoomOut();
      break;
  }
  if (handled) event.preventDefault();
}
</script>

<template>
  <div class="r-imgdoc">
    <div class="r-imgdoc__toolbar">
      <RBtn
        icon="mdi-page-first"
        variant="text"
        size="small"
        :tooltip="t('common.first-page')"
        :aria-label="t('common.first-page')"
        :disabled="page <= 1"
        @click="goTo(1)"
      />
      <RBtn
        icon="mdi-chevron-left"
        variant="text"
        size="small"
        class="r-imgdoc__step"
        :tooltip="t('common.previous-page')"
        :aria-label="t('common.previous-page')"
        :disabled="page <= 1"
        @click="goTo(page - 1)"
      />
      <RTextField
        v-model="pageInput"
        type="number"
        density="compact"
        variant="outlined"
        hide-details
        class="r-imgdoc__page-input"
        :aria-label="t('common.page')"
        :disabled="pageCount <= 0"
        @blur="commitPageInput"
        @keyup.enter="commitPageInput"
      />
      <span class="r-imgdoc__page-total">/ {{ pageCount }}</span>
      <RBtn
        icon="mdi-chevron-right"
        variant="text"
        size="small"
        class="r-imgdoc__step"
        :tooltip="t('common.next-page')"
        :aria-label="t('common.next-page')"
        :disabled="page >= pageCount"
        @click="goTo(page + 1)"
      />
      <RBtn
        icon="mdi-page-last"
        variant="text"
        size="small"
        :tooltip="t('common.last-page')"
        :aria-label="t('common.last-page')"
        :disabled="page >= pageCount"
        @click="goTo(pageCount)"
      />

      <span class="r-imgdoc__spacer" />

      <ViewerZoomControls
        :zoom="zoom"
        :fit="fit"
        :can-zoom-in="canZoomIn"
        :can-zoom-out="canZoomOut"
        @zoom-in="zoomIn"
        @zoom-out="zoomOut"
        @toggle-fit="toggleFit"
      />

      <span class="r-imgdoc__spacer" />

      <RBtn
        icon="mdi-download"
        variant="text"
        size="small"
        :href="downloadUrl"
        :download="fileName"
        :tooltip="t('common.download')"
        :aria-label="t('common.download')"
      />
      <RBtn
        v-if="redownloadable"
        icon="mdi-cloud-download-outline"
        variant="text"
        size="small"
        :tooltip="t('rom.redownload')"
        :aria-label="t('rom.redownload')"
        :loading="redownloading"
        :disabled="redownloading"
        @click="emit('redownload')"
      />
      <RBtn
        v-if="deletable"
        icon="mdi-delete-outline"
        variant="text"
        size="small"
        color="danger"
        :tooltip="t('common.delete')"
        :aria-label="t('common.delete')"
        @click="emit('delete')"
      />
    </div>

    <RProgressLinear
      :model-value="progress * 100"
      :height="2"
      :aria-label="t('rom.reading-progress')"
      class="r-imgdoc__progress"
    />

    <div class="r-imgdoc__viewer">
      <div v-if="countLoading" class="r-imgdoc__center">
        <RSpinner :size="28" />
      </div>
      <REmptyState
        v-else-if="countFailed || imageFailed"
        icon="mdi-file-alert-outline"
        :title="t('rom.manual-load-failed')"
      >
        <template #actions>
          <RBtn
            variant="outlined"
            size="small"
            @click="countFailed ? loadCount() : (imageFailed = false)"
          >
            {{ t("common.try-again") }}
          </RBtn>
        </template>
      </REmptyState>
      <REmptyState
        v-else-if="pageCount === 0"
        icon="mdi-book-open-blank-variant-outline"
        :title="t('rom.image-doc-no-pages')"
      />
      <div
        v-else
        ref="stage"
        class="r-imgdoc__stage"
        :class="`r-imgdoc__stage--${fit}`"
        :style="{ '--r-imgdoc-zoom': zoom }"
      >
        <div class="r-imgdoc__page">
          <img
            :key="pageSrc"
            :src="pageSrc"
            :alt="`${t('common.page')} ${page} / ${pageCount}`"
            class="r-imgdoc__img"
            draggable="false"
            @load="onImageLoad"
            @error="onImageError"
          />
          <!-- aria-disabled, not disabled: they hold focus for the page keys. -->
          <button
            type="button"
            class="r-imgdoc__turn r-imgdoc__turn--prev"
            :aria-label="t('common.previous-page')"
            :aria-disabled="page <= 1"
            @click="goTo(page - 1)"
            @keydown="onTurnKeydown"
          />
          <button
            type="button"
            class="r-imgdoc__turn r-imgdoc__turn--next"
            :aria-label="t('common.next-page')"
            :aria-disabled="page >= pageCount"
            @click="goTo(page + 1)"
            @keydown="onTurnKeydown"
          />
        </div>
        <div v-if="imageLoading" class="r-imgdoc__loading">
          <RSpinner :size="28" />
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-imgdoc {
  display: flex;
  flex-direction: column;
  height: 100%;
  min-height: 0;
}
.r-imgdoc__toolbar {
  display: flex;
  align-items: center;
  gap: 2px;
  padding: 6px 10px;
}
.r-imgdoc__spacer {
  flex: 1;
}
.r-imgdoc__page-input {
  width: 64px;
  flex: none;
  margin-left: 6px;
}
.r-imgdoc__page-total {
  font-size: 12px;
  color: var(--r-color-fg-muted);
  margin: 0 6px 0 4px;
  font-variant-numeric: tabular-nums;
  white-space: nowrap;
}
/* First/last page still cover paging on the narrowest toolbar. */
html[data-bp~="xs"] .r-imgdoc__step {
  display: none;
}
.r-imgdoc__progress {
  flex-shrink: 0;
}
.r-imgdoc__viewer {
  flex: 1;
  min-height: 0;
  display: flex;
  overflow: hidden;
}
.r-imgdoc__center {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
}
.r-imgdoc__stage {
  position: relative;
  flex: 1;
  min-height: 0;
  overflow: auto;
  user-select: none;
  background: var(--r-color-bg);
}
.r-imgdoc__page {
  position: relative;
}
/* Centred while smaller than the stage. Flex auto margins drop to zero once
   the page overflows, so it then starts at the top-left and scrolls. */
.r-imgdoc__stage--page {
  display: flex;
}
.r-imgdoc__stage--page .r-imgdoc__page {
  flex: none;
  width: calc(100% * var(--r-imgdoc-zoom));
  height: calc(100% * var(--r-imgdoc-zoom));
  margin: auto;
}
.r-imgdoc__stage--width .r-imgdoc__page {
  width: calc(100% * var(--r-imgdoc-zoom));
  margin: 0 auto;
}
.r-imgdoc__stage--page .r-imgdoc__img {
  display: block;
  width: 100%;
  height: 100%;
  object-fit: contain;
}
.r-imgdoc__stage--width .r-imgdoc__img {
  display: block;
  width: 100%;
  height: auto;
}
.r-imgdoc__turn {
  position: absolute;
  top: 0;
  bottom: 0;
  width: 50%;
  padding: 0;
  border: 0;
  background: transparent;
  cursor: pointer;
  /* The stage clips overflow, so the global focus ring is drawn inside. */
  outline-offset: -3px;
}
.r-imgdoc__turn[aria-disabled="true"] {
  cursor: default;
}
.r-imgdoc__turn--prev {
  left: 0;
}
.r-imgdoc__turn--next {
  right: 0;
}
.r-imgdoc__loading {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  pointer-events: none;
}
</style>
