<script setup lang="ts">
// DeleteFirmwareDialog — RDialog that confirms deletion of one or more
// firmware files and lets the user opt-in (per item) to also delete
// the underlying file from disk. The actual deletion is performed by
// the parent (FirmwareDrawer) via the `onConfirm` prop so the dialog
// stays focused on the UI flow; ConfirmDialog can't express the
// per-item filesystem checkbox so we keep a dedicated component.
//
// `onConfirm` is awaited so the confirm button stays in `:loading`
// while the request is in flight, then either closes the dialog on
// success or stays open on rejection (the parent surfaces the error).
import { RBtn, RCheckbox, RDialog, RIcon } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { FirmwareSchema } from "@/__generated__";
import { formatBytes } from "@/utils";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  modelValue: boolean;
  firmware: FirmwareSchema[];
  /** Performs the actual delete. Resolves on success (dialog closes)
   *  or rejects on failure (dialog stays open). */
  onConfirm: (
    firmware: FirmwareSchema[],
    deleteFromFs: number[],
  ) => Promise<void>;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
}>();

const { t } = useI18n();

const deleteFromFs = ref<Set<number>>(new Set());
const deleting = ref(false);

// Each open trip starts with no filesystem deletes selected — the
// user has to opt in deliberately. Resetting when modelValue flips
// from false → true prevents a previous-session selection from
// resurfacing.
watch(
  () => props.modelValue,
  (open) => {
    if (open) {
      deleteFromFs.value = new Set();
    }
  },
);

const allOnFs = computed(
  () =>
    props.firmware.length > 0 &&
    deleteFromFs.value.size === props.firmware.length,
);
const someOnFs = computed(
  () =>
    deleteFromFs.value.size > 0 &&
    deleteFromFs.value.size < props.firmware.length,
);
const fsCount = computed(() => deleteFromFs.value.size);

function toggleAllFs() {
  if (allOnFs.value) {
    deleteFromFs.value = new Set();
  } else {
    deleteFromFs.value = new Set(props.firmware.map((f) => f.id));
  }
}

function toggleFs(id: number) {
  const next = new Set(deleteFromFs.value);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  deleteFromFs.value = next;
}

function closeDialog() {
  if (deleting.value) return;
  emit("update:modelValue", false);
}

async function confirm() {
  if (deleting.value) return;
  deleting.value = true;
  try {
    await props.onConfirm(props.firmware, Array.from(deleteFromFs.value));
    emit("update:modelValue", false);
  } catch {
    // Parent surfaces the snackbar; we just stay open so the user can
    // retry or cancel.
  } finally {
    deleting.value = false;
  }
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-delete"
    :width="560"
    @update:model-value="$emit('update:modelValue', $event)"
    @close="closeDialog"
  >
    <template #header>
      <span>
        {{ t("platform.removing-firmware", firmware.length) }}
      </span>
    </template>

    <template #content>
      <p class="r-v2-del-fw__hint">
        {{
          t(
            "platform.firmware-select-to-remove",
            "Select which files to also remove from disk. Unchecked rows are only removed from the database.",
          )
        }}
      </p>

      <div v-if="firmware.length > 1" class="r-v2-del-fw__bulk">
        <RCheckbox
          :model-value="allOnFs"
          :indeterminate="someOnFs"
          hide-details
          :label="
            t(
              'platform.firmware-toggle-all-fs',
              'Also delete all files from filesystem',
            )
          "
          @update:model-value="toggleAllFs"
        />
      </div>

      <ul class="r-v2-del-fw__list">
        <li
          v-for="f in firmware"
          :key="f.id"
          class="r-v2-del-fw__row"
          :class="{ 'r-v2-del-fw__row--fs': deleteFromFs.has(f.id) }"
        >
          <RCheckbox
            :model-value="deleteFromFs.has(f.id)"
            hide-details
            class="r-v2-del-fw__row-check"
            @update:model-value="toggleFs(f.id)"
          />
          <div class="r-v2-del-fw__row-body">
            <span class="r-v2-del-fw__row-name">{{ f.file_name }}</span>
            <span class="r-v2-del-fw__row-meta">
              {{ formatBytes(f.file_size_bytes) }} ·
              <span class="r-v2-del-fw__row-hash">{{ f.md5_hash }}</span>
            </span>
          </div>
        </li>
      </ul>

      <!-- Warning strip — only painted when at least one row will hit
           the filesystem, so the destructive consequence is impossible
           to miss. -->
      <p v-if="fsCount > 0" class="r-v2-del-fw__warn">
        <RIcon icon="mdi-alert" size="14" color="var(--r-color-danger-fg)" />
        <span>
          <strong>{{ t("common.warning") }}:</strong>
          {{
            t("platform.firmware-remove-warning", fsCount, {
              named: { count: fsCount },
            })
          }}
        </span>
      </p>
    </template>

    <template #footer>
      <RBtn variant="text" :disabled="deleting" @click="closeDialog">
        {{ t("common.cancel") }}
      </RBtn>
      <RBtn
        variant="flat"
        color="danger"
        prepend-icon="mdi-delete"
        :loading="deleting"
        @click="confirm"
      >
        {{ t("common.confirm") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-del-fw__hint {
  margin: 0 0 14px;
  color: var(--r-color-fg-muted);
  font-size: 13px;
  line-height: 1.5;
}

.r-v2-del-fw__bulk {
  padding: 10px 12px;
  margin-bottom: 10px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-v2-del-fw__list {
  list-style: none;
  margin: 0;
  padding: 0;
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
  background: var(--r-color-bg-elevated);
  overflow: hidden;
}

.r-v2-del-fw__row {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 10px;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--r-color-border);
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-del-fw__row:last-child {
  border-bottom: 0;
}
.r-v2-del-fw__row--fs {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 8%,
    transparent
  );
}

.r-v2-del-fw__row-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}
.r-v2-del-fw__row-name {
  font-size: 13px;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.r-v2-del-fw__row-meta {
  font-size: 11px;
  color: var(--r-color-fg-muted);
}
.r-v2-del-fw__row-hash {
  font-family: var(--r-font-family-mono, monospace);
}

.r-v2-del-fw__warn {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  margin: 12px 0 0;
  padding: 10px 12px;
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 10%,
    transparent
  );
  border: 1px solid
    color-mix(in srgb, var(--r-color-status-base-danger) 25%, transparent);
  border-radius: var(--r-radius-md);
  color: var(--r-color-fg);
  font-size: 12px;
  line-height: 1.4;
}
.r-v2-del-fw__warn strong {
  color: var(--r-color-danger-fg);
}
</style>
