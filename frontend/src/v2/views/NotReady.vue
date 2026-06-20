<script setup lang="ts">
import { RBtn } from "@v2/lib";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import { useUiVersion } from "@/composables/useUiVersion";

const { t } = useI18n();
const route = useRoute();
const uiVersion = useUiVersion();

function switchToV1() {
  uiVersion.value = "v1";
}
</script>

<template>
  <section class="r-v2-notready">
    <h1>{{ t("common.v2-not-available-title") }}</h1>
    <i18n-t keypath="common.v2-not-migrated" tag="p">
      <template #view>
        <code>{{ route.fullPath }}</code>
      </template>
    </i18n-t>
    <RBtn color="primary" @click="switchToV1">
      {{ t("common.v2-switch-back") }}
    </RBtn>
  </section>
</template>

<style scoped>
.r-v2-notready {
  max-width: 640px;
  margin: 0 auto;
  padding: var(--r-space-8);
  text-align: center;
  color: var(--r-color-fg);
}

.r-v2-notready h1 {
  font-size: var(--r-font-size-2xl);
  font-weight: var(--r-font-weight-semibold);
  margin-bottom: var(--r-space-4);
}

.r-v2-notready p {
  color: var(--r-color-fg-muted);
  margin-bottom: var(--r-space-6);
}

.r-v2-notready code {
  font-family: var(--r-font-family-mono);
  background-color: var(--r-color-surface);
  padding: 2px 6px;
  border-radius: var(--r-radius-sm);
}
</style>
