<script setup lang="ts">
// PasswordField — RTextField with the show/hide eye toggle baked in.
// The eye icon (and its click listener) is the only bit Vuetify makes
// tab-focusable by design, so consumers don't have to re-wire it in
// every auth / settings form.
import { RTextField } from "@v2/lib";
import { ref } from "vue";

defineOptions({ inheritAttrs: false });

withDefaults(
  defineProps<{
    modelValue?: string;
    label?: string;
    autocomplete?: string;
    disabled?: boolean;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    rules?: Array<(value: any) => true | string>;
    prependInnerIcon?: string;
    variant?: "outlined" | "filled" | "underlined" | "plain";
  }>(),
  {
    modelValue: "",
    label: undefined,
    autocomplete: "current-password",
    rules: undefined,
    prependInnerIcon: "mdi-lock",
    variant: "underlined",
  },
);

defineEmits<{
  (e: "update:modelValue", value: string): void;
}>();

const visible = ref(false);
</script>

<template>
  <RTextField
    v-bind="$attrs"
    :model-value="modelValue"
    :label="label"
    :type="visible ? 'text' : 'password'"
    :variant="variant"
    :prepend-inner-icon="prependInnerIcon"
    :append-inner-icon="visible ? 'mdi-eye-off' : 'mdi-eye'"
    :autocomplete="autocomplete"
    :disabled="disabled"
    :rules="rules"
    @update:model-value="(v: string) => $emit('update:modelValue', v)"
    @click:append-inner="visible = !visible"
  />
</template>
