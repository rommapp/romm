<script setup lang="ts">
import { RAlert, RBtn } from "@v2/lib";
import { useI18n } from "vue-i18n";

defineEmits<{ (e: "retry"): void }>();

const { t } = useI18n();
</script>

<template>
  <RAlert type="error" :text="t('common.markdown-load-error')">
    <template #actions>
      <RBtn variant="text" @click="$emit('retry')">
        {{ t("common.try-again") }}
      </RBtn>
    </template>
  </RAlert>
</template>
