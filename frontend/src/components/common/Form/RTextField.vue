<script setup lang="ts">
import { computed, ref } from "vue";
import { useI18n } from "vue-i18n";

const { t } = useI18n();

const props = withDefaults(
  defineProps<{
    modelValue: string | null;
    label?: string;
    type?: string;
    placeholder?: string;
    variant?:
      | "outlined"
      | "filled"
      | "plain"
      | "underlined"
      | "solo"
      | "solo-inverted"
      | "solo-filled";
    rules?: ((value: string) => boolean | string)[];
    errorMessages?: string | string[];
    disabled?: boolean;
    readonly?: boolean;
    required?: boolean;
    toggleable?: boolean;
  }>(),
  {
    label: "",
    type: "text",
    placeholder: "",
    variant: "outlined",
    rules: () => [],
    errorMessages: "",
    disabled: false,
    readonly: false,
    required: false,
    toggleable: false,
  },
);

const showPassword = ref(false);

const computedRules = computed(() => {
  const allRules = [...(props.rules || [])];
  return props.required
    ? [...allRules, (value: string) => !!value || t("common.required")]
    : allRules;
});

const computedType = computed(() => {
  if (props.toggleable) {
    return showPassword.value ? "text" : "password";
  }
  return props.type;
});

const computedAppendIcon = computed(() => {
  if (props.toggleable) {
    return showPassword.value ? "mdi-eye-off" : "mdi-eye";
  }
  return undefined;
});

function togglePasswordVisibility() {
  props.toggleable && (showPassword.value = !showPassword.value);
}

defineEmits(["update:modelValue"]);
</script>
<template>
  <v-text-field
    v-bind="$attrs"
    :model-value="modelValue"
    :label="label"
    :type="computedType"
    :variant="variant"
    :placeholder="placeholder"
    :rules="computedRules"
    :error-messages="errorMessages"
    :disabled="disabled"
    :readonly="readonly"
    :append-inner-icon="computedAppendIcon"
    @update:model-value="$emit('update:modelValue', $event)"
    @click:append-inner="togglePasswordVisibility"
  />
</template>
