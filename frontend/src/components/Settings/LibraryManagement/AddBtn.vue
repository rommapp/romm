<script setup lang="ts">
import { useI18n } from "vue-i18n";

// Props
withDefaults(
  defineProps<{
    enabled?: boolean;
  }>(),
  { enabled: false },
);
const { t } = useI18n();
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
      {{ t("common.add") }}
    </v-btn>
  </v-expand-transition>
</template>
