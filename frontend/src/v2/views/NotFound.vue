<script setup lang="ts">
import { RBtn, REmptyState } from "@v2/lib";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";

const { t } = useI18n();
</script>

<template>
  <section class="r-v2-notfound">
    <REmptyState
      icon="mdi-map-marker-question-outline"
      :hint="t('emptyStates.404-subtitle')"
    >
      <template #title>
        <p class="r-v2-notfound__code">404</p>
        <h1 class="r-v2-notfound__title">{{ t("emptyStates.404-title") }}</h1>
      </template>
      <template #actions>
        <RBtn
          color="primary"
          prepend-icon="mdi-home-outline"
          :to="{ name: ROUTES.HOME }"
        >
          {{ t("common.home") }}
        </RBtn>
      </template>
    </REmptyState>
  </section>
</template>

<style scoped>
.r-v2-notfound {
  max-width: 640px;
  margin: 0 auto;
  padding: var(--r-space-8);
}

.r-v2-notfound__code {
  margin: 0;
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-2xl);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-faint);
}

.r-v2-notfound__title {
  margin: 0;
  font-size: var(--r-font-size-xl);
  font-weight: var(--r-font-weight-semibold);
}
</style>
