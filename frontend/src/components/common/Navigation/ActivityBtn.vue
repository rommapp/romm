<script setup lang="ts">
import { onMounted } from "vue";
import { useI18n } from "vue-i18n";
import storeActivity from "@/stores/activity";
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
const activityStore = storeActivity();

onMounted(() => {
  activityStore.initSocket();
  if (!activityStore.initialized) {
    activityStore.fetchAll();
  }
});
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
    @click="navigationStore.goActivity"
  >
    <div class="d-flex flex-column align-center">
      <v-badge
        :model-value="activityStore.activeCount > 0"
        :content="activityStore.activeCount"
        color="success"
        offset-x="-2"
        offset-y="-2"
      >
        <v-icon :color="$route.path.startsWith('/activity') ? 'primary' : ''">
          mdi-access-point
        </v-icon>
      </v-badge>
      <v-expand-transition>
        <span
          v-if="withTag"
          class="text-caption text-center"
          :class="{ 'text-primary': $route.path.startsWith('/activity') }"
        >
          {{ t("common.activity") }}
        </span>
      </v-expand-transition>
    </div>
  </v-btn>
</template>
