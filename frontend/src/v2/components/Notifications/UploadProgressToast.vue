<script setup lang="ts">
// UploadProgressToast — persistent bottom-right panel tracking every
// active upload in the shared `storeUpload`. Shows filename, progress bar
// + speed + bytes for in-flight files, a check for completed files, and
// the failure reason for failed files. Collapses to a pill when nothing
// is active.
import { RBtn, RIcon } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import storeUpload from "@/stores/upload";
import { formatBytes } from "@/utils";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

const uploadStore = storeUpload();
const { files } = storeToRefs(uploadStore);
const collapsed = ref(false);

const activeCount = computed(
  () => files.value.filter((f) => !f.finished && !f.failed).length,
);
const finishedCount = computed(
  () => files.value.filter((f) => f.finished && !f.failed).length,
);
const failedCount = computed(() => files.value.filter((f) => f.failed).length);
const hasClearable = computed(() =>
  files.value.some((f) => f.finished || f.failed),
);

// Auto-expand when new uploads come in (collapsed flag resets on empty).
watch(files, (list) => {
  if (list.length === 0) collapsed.value = false;
});

function clearFinished() {
  uploadStore.clearFinished();
}
</script>

<template>
  <transition name="r-v2-upload">
    <div
      v-if="files.length > 0"
      class="r-v2-upload"
      role="region"
      :aria-label="t('common.upload-progress')"
    >
      <header class="r-v2-upload__head">
        <div class="r-v2-upload__summary">
          <RIcon
            :icon="
              activeCount > 0
                ? 'mdi-cloud-upload-outline'
                : failedCount > 0
                  ? 'mdi-alert-circle-outline'
                  : 'mdi-check-circle-outline'
            "
            size="16"
          />
          <span v-if="activeCount > 0">
            {{
              t("common.uploading-files-n", activeCount, {
                named: { n: activeCount },
              })
            }}
          </span>
          <span v-else-if="failedCount > 0">
            {{
              t("common.upload-stats", {
                done: finishedCount,
                failed: failedCount,
              })
            }}
          </span>
          <span v-else>
            {{ t("common.uploaded-n", { n: finishedCount }) }}
          </span>
        </div>
        <button
          type="button"
          class="r-v2-upload__toggle"
          :aria-label="
            collapsed
              ? t('common.upload-expand-panel')
              : t('common.upload-collapse-panel')
          "
          :aria-expanded="!collapsed"
          @click="collapsed = !collapsed"
        >
          <RIcon
            :icon="collapsed ? 'mdi-chevron-up' : 'mdi-chevron-down'"
            size="16"
          />
        </button>
      </header>

      <ul v-if="!collapsed" class="r-v2-upload__list">
        <li
          v-for="file in files"
          :key="file.filename"
          class="r-v2-upload__item"
          :class="{
            'r-v2-upload__item--done': file.finished && !file.failed,
            'r-v2-upload__item--failed': file.failed,
          }"
        >
          <div class="r-v2-upload__item-head">
            <span class="r-v2-upload__filename" :title="file.filename">
              {{ file.filename }}
            </span>
            <RIcon
              :icon="
                file.failed
                  ? 'mdi-close-circle'
                  : file.finished
                    ? 'mdi-check-circle'
                    : 'mdi-progress-upload'
              "
              size="14"
              class="r-v2-upload__item-status"
              :class="{
                'r-v2-upload__item-status--spin':
                  !file.finished && !file.failed,
              }"
            />
          </div>
          <template v-if="file.failed">
            <p v-if="file.failureReason" class="r-v2-upload__error">
              {{ file.failureReason }}
            </p>
          </template>
          <template v-else-if="!file.finished && file.progress > 0">
            <div class="r-v2-upload__bar" aria-hidden="true">
              <div
                class="r-v2-upload__bar-fill"
                :style="{ width: `${file.progress}%` }"
              />
            </div>
            <div class="r-v2-upload__item-meta">
              <span>{{ formatBytes(file.rate) }}/s</span>
              <span>
                {{ formatBytes(file.loaded) }} / {{ formatBytes(file.total) }}
              </span>
            </div>
          </template>
          <template v-else-if="file.finished">
            <div class="r-v2-upload__item-meta">
              <span />
              <span>{{ formatBytes(file.total) }}</span>
            </div>
          </template>
        </li>
      </ul>

      <footer v-if="!collapsed && hasClearable" class="r-v2-upload__foot">
        <RBtn
          size="small"
          variant="text"
          color="primary"
          @click="clearFinished"
        >
          {{ t("common.clear-finished") }}
        </RBtn>
      </footer>
    </div>
  </transition>
</template>

<style scoped>
.r-v2-upload {
  position: fixed;
  right: 16px;
  bottom: 16px;
  z-index: 8900;
  width: min(360px, calc(100vw - 32px));
  background: var(--r-color-toast-bg);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  -webkit-backdrop-filter: blur(18px);
  box-shadow:
    0 18px 36px color-mix(in srgb, black 50%, transparent),
    0 4px 10px color-mix(in srgb, black 30%, transparent);
  overflow: hidden;
}

.r-v2-upload__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--r-color-border);
}

.r-v2-upload__summary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  flex: 1;
  min-width: 0;
}

.r-v2-upload__toggle {
  appearance: none;
  background: transparent;
  border: 0;
  color: var(--r-color-fg-secondary);
  width: 26px;
  height: 26px;
  border-radius: 6px;
  display: grid;
  place-items: center;
  cursor: pointer;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-upload__toggle:hover {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

.r-v2-upload__list {
  list-style: none;
  margin: 0;
  padding: 4px 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 320px;
  overflow-y: auto;
}

.r-v2-upload__item {
  padding: 8px 10px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-bg-elevated);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-upload__item--done {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 6%,
    transparent
  );
}
.r-v2-upload__item--failed {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 8%,
    transparent
  );
}

.r-v2-upload__item-head {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: center;
}

.r-v2-upload__filename {
  font-size: 12.5px;
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.r-v2-upload__item-status {
  color: var(--r-color-fg-secondary);
}
.r-v2-upload__item--done .r-v2-upload__item-status {
  color: var(--r-color-success);
}
.r-v2-upload__item--failed .r-v2-upload__item-status {
  color: var(--r-color-danger-fg);
}
.r-v2-upload__item-status--spin {
  color: var(--r-color-brand-primary);
  animation: r-v2-upload-spin 1s linear infinite;
}
@keyframes r-v2-upload-spin {
  to {
    transform: rotate(360deg);
  }
}

.r-v2-upload__bar {
  height: 3px;
  width: 100%;
  background: var(--r-color-surface);
  border-radius: var(--r-radius-pill);
  margin-top: 6px;
  overflow: hidden;
}
.r-v2-upload__bar-fill {
  height: 100%;
  background: var(--r-color-brand-primary);
  transition: width 150ms linear;
}

.r-v2-upload__item-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
  font-size: 10px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

.r-v2-upload__error {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--r-color-danger-fg);
  line-height: 1.35;
}

.r-v2-upload__foot {
  padding: 4px 8px 8px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--r-color-border);
}

/* Slide + fade in/out from the bottom-right. */
.r-v2-upload-enter-from,
.r-v2-upload-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
.r-v2-upload-enter-active,
.r-v2-upload-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}

html[data-bp~="xs"] .r-v2-upload {
  left: 12px;
  right: 12px;
  width: auto;
  bottom: 12px;
}
</style>
