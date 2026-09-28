<script setup lang="ts">
// Files waiting to be sent: a drop zone while empty, then the list with an
// "Add" button and per-row removal. Files dedupe by name.
import { RBtn, RChip, RDropzone, RIcon } from "@v2/lib";
import { ref } from "vue";
import { useI18n } from "vue-i18n";
import { formatBytes } from "@/utils";

defineOptions({ inheritAttrs: false });

const props = withDefaults(
  defineProps<{
    modelValue: File[];
    inputLabel: string;
    multiple?: boolean;
    disabled?: boolean;
  }>(),
  { multiple: true, disabled: false },
);

const emit = defineEmits<{
  "update:modelValue": [files: File[]];
}>();

const { t } = useI18n();

const filledDz = ref<InstanceType<typeof RDropzone> | null>(null);

function addFiles(picked: File[]) {
  const seen = new Set(props.modelValue.map((f) => f.name));
  emit("update:modelValue", [
    ...props.modelValue,
    ...picked.filter((f) => !seen.has(f.name)),
  ]);
}

function removeFile(name: string) {
  emit(
    "update:modelValue",
    props.modelValue.filter((f) => f.name !== name),
  );
}

defineExpose({ open: () => filledDz.value?.open() });
</script>

<template>
  <RDropzone
    v-if="modelValue.length === 0"
    :title="t('common.dropzone-title')"
    :hint="t('common.dropzone-hint')"
    :active-title="t('common.dropzone-drag-over')"
    :input-label="inputLabel"
    :multiple="multiple"
    :disabled="disabled"
    @files="addFiles"
  />
  <RDropzone
    v-else
    ref="filledDz"
    overlay
    :release-label="t('common.dropzone-drag-over')"
    :input-label="inputLabel"
    :multiple="multiple"
    :disabled="disabled"
    @files="addFiles"
  >
    <div class="r-pending-files">
      <header class="r-pending-files__head">
        <span>
          {{ t("common.upload-files-selected", { count: modelValue.length }) }}
        </span>
        <RBtn
          variant="flat"
          color="primary"
          prepend-icon="mdi-plus"
          @click="filledDz?.open()"
        >
          {{ t("common.add") }}
        </RBtn>
      </header>
      <ul class="r-pending-files__list">
        <li v-for="f in modelValue" :key="f.name" class="r-pending-files__row">
          <RIcon icon="mdi-file-outline" size="14" />
          <span class="r-pending-files__name">{{ f.name }}</span>
          <RChip size="x-small" variant="translucent">
            {{ formatBytes(f.size) }}
          </RChip>
          <RBtn
            variant="text"
            size="x-small"
            icon="mdi-close"
            color="danger"
            :aria-label="t('common.remove')"
            @click="removeFile(f.name)"
          />
        </li>
      </ul>
    </div>
  </RDropzone>
</template>

<style scoped>
.r-pending-files {
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.r-pending-files__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  font-size: 0.85rem;
}

.r-pending-files__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 4px;
  max-height: 240px;
  overflow-y: auto;
}

.r-pending-files__row {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.r-pending-files__name {
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 0.85rem;
}
</style>
