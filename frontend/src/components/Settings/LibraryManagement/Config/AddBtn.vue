<script setup lang="ts">
import { useI18n } from "vue-i18n";

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
      size="large"
      rounded="0"
      prepend-icon="mdi-plus"
      variant="outlined"
      class="text-primary"
      @click="$emit('click')"
    >
      {{ t("common.add") }}
    </v-btn>
  </v-expand-transition>
</template>
