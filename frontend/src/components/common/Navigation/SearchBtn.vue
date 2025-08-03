<script setup lang="ts">
import storeNavigation from "@/stores/navigation";
import { useI18n } from "vue-i18n";
import { ref } from "vue";
import { useNavigation } from "@/composables/useNavigation";

// Props
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

const searchBtnRef = ref<HTMLElement>();

useNavigation(searchBtnRef, "search-btn", {
  priority: 2,
  action: () => navigationStore.goSearch(),
});
</script>
<template>
  <v-btn
    ref="searchBtnRef"
    icon
    :block="block"
    variant="flat"
    color="background"
    :height="height"
    :class="{ rounded: rounded }"
    class="py-4 bg-background d-flex align-center justify-center"
    @click="navigationStore.goSearch"
    v-navigation="{ id: 'search-btn', priority: 2 }"
  >
    <div class="d-flex flex-column align-center">
      <v-icon :color="$route.name == 'search' ? 'primary' : ''"
        >mdi-magnify</v-icon
      >
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
