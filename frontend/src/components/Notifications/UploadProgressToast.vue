<script setup lang="ts">
// UploadProgressToast: persistent bottom-right panel tracking every
// active upload in the shared `storeUpload`. Shows filename, progress bar
// + speed + bytes for in-flight files, a check for completed files, and
// the failure reason for failed files. Collapses to a pill when nothing
// is active.
import { storeToRefs } from "pinia";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { RBtn, RIcon } from "@/lib";
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
  <transition name="r-upload">
    <div
      v-if="files.length > 0"
      class="r-upload"
      role="region"
      :aria-label="t('common.upload-progress')"
    >
      <header class="r-upload__head">
        <div class="r-upload__summary">
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
          class="r-upload__toggle"
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

      <ul v-if="!collapsed" class="r-upload__list">
        <li
          v-for="file in files"
          :key="file.filename"
          class="r-upload__item"
          :class="{
            'r-upload__item--done': file.finished && !file.failed,
            'r-upload__item--failed': file.failed,
          }"
        >
          <div class="r-upload__item-head">
            <span class="r-upload__filename" :title="file.filename">
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
              class="r-upload__item-status"
              :class="{
                'r-upload__item-status--spin': !file.finished && !file.failed,
              }"
            />
          </div>
          <template v-if="file.failed">
            <p v-if="file.failureReason" class="r-upload__error">
              {{ file.failureReason }}
            </p>
          </template>
          <template v-else-if="!file.finished && file.progress > 0">
            <div class="r-upload__bar" aria-hidden="true">
              <div
                class="r-upload__bar-fill"
                :style="{ width: `${file.progress}%` }"
              />
            </div>
            <div class="r-upload__item-meta">
              <span>{{ formatBytes(file.rate) }}/s</span>
              <span>
                {{ formatBytes(file.loaded) }} / {{ formatBytes(file.total) }}
              </span>
            </div>
          </template>
          <template v-else-if="file.finished">
            <div class="r-upload__item-meta">
              <span />
              <span>{{ formatBytes(file.total) }}</span>
            </div>
          </template>
        </li>
      </ul>

      <footer v-if="!collapsed && hasClearable" class="r-upload__foot">
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
.r-upload {
  position: fixed;
  right: calc(16px + var(--r-safe-r));
  bottom: calc(16px + var(--r-safe-b));
  z-index: 8900;
  width: min(360px, calc(100vw - 32px));
  background: var(--r-color-toast-bg);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(18px);
  box-shadow:
    0 18px 36px color-mix(in srgb, black 50%, transparent),
    0 4px 10px color-mix(in srgb, black 30%, transparent);
  overflow: hidden;
}

.r-upload__head {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--r-color-border);
}

.r-upload__summary {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  flex: 1;
  min-width: 0;
}

.r-upload__toggle {
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
.r-upload__toggle:hover {
  background: var(--r-color-surface);
  color: var(--r-color-fg);
}

.r-upload__list {
  list-style: none;
  margin: 0;
  padding: 4px 6px;
  display: flex;
  flex-direction: column;
  gap: 2px;
  max-height: 320px;
  overflow-y: auto;
}

.r-upload__item {
  padding: 8px 10px;
  border-radius: var(--r-radius-sm);
  background: var(--r-color-bg-elevated);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-upload__item--done {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 6%,
    transparent
  );
}
.r-upload__item--failed {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 8%,
    transparent
  );
}

.r-upload__item-head {
  display: grid;
  grid-template-columns: 1fr auto;
  gap: 8px;
  align-items: center;
}

.r-upload__filename {
  font-size: 12.5px;
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  min-width: 0;
}

.r-upload__item-status {
  color: var(--r-color-fg-secondary);
}
.r-upload__item--done .r-upload__item-status {
  color: var(--r-color-success);
}
.r-upload__item--failed .r-upload__item-status {
  color: var(--r-color-danger-fg);
}
.r-upload__item-status--spin {
  color: var(--r-color-brand-primary);
  animation: r-upload-spin 1s linear infinite;
}
@keyframes r-upload-spin {
  to {
    transform: rotate(360deg);
  }
}

.r-upload__bar {
  height: 3px;
  width: 100%;
  background: var(--r-color-surface);
  border-radius: var(--r-radius-pill);
  margin-top: 6px;
  overflow: hidden;
}
.r-upload__bar-fill {
  height: 100%;
  background: var(--r-color-brand-primary);
  transition: width 150ms linear;
}

.r-upload__item-meta {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  margin-top: 4px;
  font-size: 10px;
  color: var(--r-color-fg-muted);
  font-variant-numeric: tabular-nums;
}

.r-upload__error {
  margin: 4px 0 0;
  font-size: 11px;
  color: var(--r-color-danger-fg);
  line-height: 1.35;
}

.r-upload__foot {
  padding: 4px 8px 8px;
  display: flex;
  justify-content: flex-end;
  border-top: 1px solid var(--r-color-border);
}

/* Slide + fade in/out from the bottom-right. */
.r-upload-enter-from,
.r-upload-leave-to {
  opacity: 0;
  transform: translateY(12px);
}
.r-upload-enter-active,
.r-upload-leave-active {
  transition:
    opacity var(--r-motion-med) var(--r-motion-ease-out),
    transform var(--r-motion-med) var(--r-motion-ease-out);
}

html[data-bp~="xs"] .r-upload {
  left: 12px;
  right: 12px;
  width: auto;
  bottom: calc(12px + var(--r-safe-b));
}
</style>
