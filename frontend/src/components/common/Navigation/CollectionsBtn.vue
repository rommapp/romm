<script setup lang="ts">
import { storeToRefs } from "pinia";
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
const { activeCollectionsDrawer } = storeToRefs(navigationStore);
</script>
<template>
  <v-btn
    icon
    :block="block"
    variant="flat"
    :height="height"
    class="py-4 bg-background d-flex align-center justify-center"
    :class="{ rounded: rounded }"
    :color="activeCollectionsDrawer ? 'toplayer' : 'background'"
    @click="navigationStore.switchActiveCollectionsDrawer"
  >
    <div class="d-flex flex-column align-center">
      <v-icon
        :color="
          $route.name == 'collection' ||
          $route.name == 'virtual-collection' ||
          $route.name == 'smart-collection'
            ? 'primary'
            : ''
        "
      >
        mdi-bookmark-box-multiple
      </v-icon>
      <v-expand-transition>
        <span
          v-if="withTag"
          class="text-caption text-center"
          :class="{
            'text-primary':
              $route.name == 'collection' ||
              $route.name == 'virtual-collection' ||
              $route.name == 'smart-collection',
          }"
          >{{ t("common.collections") }}</span
        >
      </v-expand-transition>
    </div>
  </v-btn>
</template>
