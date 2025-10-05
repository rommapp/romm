<script setup lang="ts">
import { useI18n } from "vue-i18n";
import storeNavigation from "@/stores/navigation";

withDefaults(
  defineProps<{
    block?: boolean;
    height?: string;
    rounded?: boolean;
    withTag?: boolean;
  }>(),
  {
    block: false,
    height: "",
    rounded: false,
    withTag: false,
  },
);
const { t } = useI18n();
const navigationStore = storeNavigation();
</script>
<template>
  <v-btn
    icon
    :block="block"
    variant="flat"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="py-4 bg-background d-flex align-center justify-center"
    @click="navigationStore.goSearch"
  >
    <div class="d-flex flex-column align-center">
      <v-icon :color="$route.name == 'search' ? 'primary' : ''">
        mdi-magnify
      </v-icon>
      <v-expand-transition>
        <span
          v-if="withTag"
          class="text-caption text-center"
          :class="{ 'text-primary': $route.name == 'search' }"
          >{{ t("common.search") }}</span
        >
      </v-expand-transition>
    </div>
  </v-btn>
</template>
