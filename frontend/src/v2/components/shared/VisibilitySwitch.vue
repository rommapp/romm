<script setup lang="ts">
// The public/private switch every edit and create form carries, labelled with
// the state it is in.
import { RSwitch } from "@v2/lib";
import { useI18n } from "vue-i18n";

withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false });

const isPublic = defineModel<boolean>({ required: true });

const { t } = useI18n();
</script>

<template>
  <RSwitch
    v-model="isPublic"
    :disabled="disabled"
    :label="isPublic ? t('common.public') : t('common.private')"
  />
</template>
