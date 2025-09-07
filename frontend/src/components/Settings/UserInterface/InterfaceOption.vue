<script setup lang="ts">
withDefaults(
  defineProps<{
    modelValue: boolean;
    title?: string;
    description?: string;
    icon?: string;
  }>(),
  { title: "", description: "", icon: "" },
);
const emit = defineEmits(["update:modelValue"]);
</script>
<template>
  <v-card elevation="0">
    <v-list-item class="px-6 py-1">
      <template #prepend>
        <v-icon :class="modelValue ? 'text-primary' : ''" :icon="icon" />
      </template>

      <v-list-item-title
        class="font-weight-bold"
        :class="{ 'text-primary': modelValue }"
      >
        {{ title }}
      </v-list-item-title>
      <v-list-item-subtitle>{{ description }}</v-list-item-subtitle>

      <template #append>
        <v-switch
          inset
          :model-value="modelValue"
          color="primary"
          hide-details
          @update:model-value="(value) => emit('update:modelValue', value)"
        />
      </template>
    </v-list-item>
  </v-card>
</template>

<style scoped>
.text-primary {
  transition: color 0.3s ease-in-out;
}

.v-list-item-title,
.v-icon {
  transition: color 0.3s ease-in-out;
}
</style>
