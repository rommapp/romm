<script setup lang="ts">
withDefaults(
  defineProps<{
    enabled?: boolean;
  }>(),
  { enabled: false }
);
const emit = defineEmits(["click"]);
</script>
<template>
  <v-expand-transition>
    <v-btn
      v-if="enabled"
      block
      rounded="0"
      size="large"
      prepend-icon="mdi-plus"
      variant="outlined"
      class="text-romm-accent-1"
      @click="$emit('click')"
    >
      Add
    </v-btn>
  </v-expand-transition>
</template>
