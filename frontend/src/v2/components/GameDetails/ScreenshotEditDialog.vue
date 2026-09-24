<script setup lang="ts">
// ScreenshotEditDialog: one of the user's gallery screenshots, where its
// visibility is set like every other shared thing's.
import { RBtn, RDialog, RForm } from "@v2/lib";
import { ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import VisibilitySwitch from "@/v2/components/shared/VisibilitySwitch.vue";

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    isPublic?: boolean;
    busy?: boolean;
  }>(),
  { isPublic: false, busy: false },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "submit", isPublic: boolean): void;
}>();

const { t } = useI18n();

const isPublic = ref(props.isPublic);

// Reopening is what resets the field, so a cancelled edit does not carry
// into the next one.
watch(
  () => props.modelValue,
  (open) => {
    if (open) isPublic.value = props.isPublic;
  },
  { immediate: true },
);

function close(): void {
  emit("update:modelValue", false);
}

function submit(): void {
  if (props.busy || isPublic.value === props.isPublic) return;
  emit("submit", isPublic.value);
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-pencil-outline"
    :width="400"
    cancelable
    :cancel-disabled="busy"
    @update:model-value="
      (v) => {
        if (!v) close();
      }
    "
  >
    <template #header>
      <span>{{ t("rom.edit-screenshot") }}</span>
    </template>

    <template #content>
      <RForm @submit="submit">
        <VisibilitySwitch v-model="isPublic" :disabled="busy" />
      </RForm>
    </template>

    <template #footer>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-check"
        :loading="busy"
        :disabled="busy || isPublic === props.isPublic"
        @click="submit"
      >
        {{ t("common.save") }}
      </RBtn>
    </template>
  </RDialog>
</template>
