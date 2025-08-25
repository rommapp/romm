<script setup lang="ts">
import { computed, onMounted } from "vue";
import NavigationText from "./NavigationText.vue";
import RDialog from "@/components/common/RDialog.vue";

const props = defineProps<{ urls: string[]; startIndex?: number }>();
const emit = defineEmits(["close"]);

const isOpen = computed({
  get: () => true,
  set: () => close(),
});

function close() {
  emit("close");
}

onMounted(() => {
  (document.activeElement as HTMLElement | null)?.blur();
});
</script>

<template>
  <r-dialog v-model="isOpen" :width="1000" class="lightbox-dialog">
    <template #header>
      <div class="d-flex justify-space-between align-center pa-4">
        <h2>Screenshots</h2>
      </div>
    </template>
    <template #content>
      <div class="position-relative">
        <v-carousel
          v-model="props.startIndex"
          hide-delimiter-background
          delimiter-icon="mdi-square"
          show-arrows="hover"
          hide-delimiters
          class="dialog-carousel"
        >
          <template #prev="{ props }">
            <v-btn
              v-if="urls.length > 1"
              icon="mdi-chevron-left"
              @click="props.onClick"
            />
          </template>

          <v-carousel-item
            v-for="screenshot in urls"
            :key="screenshot"
            :src="screenshot"
            contain
          >
            <template #placeholder>
              <div class="d-flex justify-center align-center">
                <v-progress-circular indeterminate />
              </div>
            </template>
          </v-carousel-item>

          <template #next="{ props }">
            <v-btn
              v-if="urls.length > 1"
              icon="mdi-chevron-right"
              @click="props.onClick"
            />
          </template>
        </v-carousel>
      </div>

      <div class="pa-4">
        <div class="d-flex justify-space-between align-center">
          <navigation-text
            :show-navigation="true"
            :show-select="false"
            :show-back="true"
            :show-toggle-favorite="false"
            :show-menu="false"
          />
          <div class="px-2 py-1 text-white bg-black/50 rounded">
            {{ props.startIndex ? props.startIndex + 1 : 1 }} /
            {{ urls.length }}
          </div>
        </div>
      </div>
    </template>
  </r-dialog>
</template>

<style>
.lightbox-dialog .v-overlay__content {
  max-height: 80vh;
}

.dialog-carousel {
  max-width: 1000px;
}
</style>
