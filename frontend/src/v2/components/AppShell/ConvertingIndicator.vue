<script setup lang="ts">
// Top-bar pill shown while a "Download as" conversion runs on the server. Its
// menu lists each conversion; the browser download starts when one finishes.
import { RDivider, RMenu, RMenuItem, RTag } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { ROUTES } from "@/plugins/router";
import NavStatusPill from "@/v2/components/AppShell/NavStatusPill.vue";
import NavStatusTransition from "@/v2/components/AppShell/NavStatusTransition.vue";
import storeFormatConversions from "@/v2/stores/formatConversions";

const { t } = useI18n();
const { conversions } = storeToRefs(storeFormatConversions());

const counter = computed(() =>
  conversions.value.length > 1 ? String(conversions.value.length) : null,
);
</script>

<template>
  <NavStatusTransition :show="conversions.length > 0">
    <RMenu location="bottom end" width="280px" sheet-on-mobile>
      <template #activator="{ props: menuProps }">
        <NavStatusPill
          v-bind="menuProps"
          :label="t('rom.converting')"
          icon="mdi-file-sync-outline"
          :counter="counter"
          :aria-label="
            t('rom.converting-downloads', conversions.length, {
              named: { n: conversions.length },
            })
          "
        />
      </template>

      <p class="r-v2-converting__note">
        {{ t("rom.converting-note") }}
      </p>
      <RDivider />
      <RMenuItem
        v-for="conversion in conversions"
        :key="conversion.href"
        :to="{ name: ROUTES.ROM, params: { rom: conversion.romId } }"
        icon="mdi-file-sync-outline"
        :label="conversion.romName"
      >
        <template #append>
          <RTag :text="conversion.format" size="x-small" />
        </template>
      </RMenuItem>
    </RMenu>
  </NavStatusTransition>
</template>

<style scoped>
.r-v2-converting__note {
  margin: 0;
  padding: 8px 12px;
  font-size: 12px;
  line-height: 1.4;
  color: var(--r-color-fg-muted);
}
</style>
