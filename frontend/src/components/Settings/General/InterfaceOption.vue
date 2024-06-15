<script setup lang="ts">
import { useDisplay } from "vuetify";

const { xs } = useDisplay();
withDefaults(
  defineProps<{
    modelValue: boolean;
    title?: string;
    description?: string;
    icon?: string;
  }>(),
  { title: "", description: "", icon: "" }
);
const emit = defineEmits(["update:modelValue"]);
</script>
<template>
  <v-card elevation="0">
    <v-list-item class="pa-1"
      ><template #prepend
        ><v-icon :class="modelValue ? 'text-romm-accent-1' : ''" :icon="icon"
      /></template>

      <v-list-item-title
        class="font-weight-bold"
        :class="{ 'text-romm-accent-1': modelValue }"
        >{{ title }}</v-list-item-title
      >
      <v-list-item-subtitle>{{ description }}</v-list-item-subtitle>

      <template #append>
        <v-switch
          :model-value="modelValue"
          @update:model-value="(value) => emit('update:modelValue', value)"
          :class="{ 'pr-16': !xs }"
          color="romm-accent-1"
          hide-details
        /> </template
    ></v-list-item>
  </v-card>
</template>
