<script setup lang="ts">
// The public/private switch of every edit and create form. Both labels hold
// the space, so flipping it never moves what sits beside it.
import { RSwitch } from "@v2/lib";
import { computed } from "vue";
import { useI18n } from "vue-i18n";

withDefaults(defineProps<{ disabled?: boolean }>(), { disabled: false });

const isPublic = defineModel<boolean>({ required: true });

const { t } = useI18n();

const label = computed(() =>
  isPublic.value ? t("common.public") : t("common.private"),
);
</script>

<template>
  <RSwitch v-model="isPublic" :disabled="disabled" :aria-label="label">
    <template #label>
      <span class="r-visibility-switch__label">
        <span :class="{ 'r-visibility-switch__off': !isPublic }">
          {{ t("common.public") }}
        </span>
        <span :class="{ 'r-visibility-switch__off': isPublic }">
          {{ t("common.private") }}
        </span>
      </span>
    </template>
  </RSwitch>
</template>

<style scoped>
.r-visibility-switch__label {
  display: inline-grid;
}
.r-visibility-switch__label > span {
  grid-area: 1 / 1;
}
.r-visibility-switch__off {
  visibility: hidden;
}
</style>
