<script setup lang="ts">
import { computed, ref } from "vue";
import type { Walkthrough } from "@/composables/useWalkthrough";
import type { DetailedRom } from "@/stores/roms";
import WalkthroughModal from "./WalkthroughModal.vue";
import WalkthroughProgress from "./WalkthroughProgress.vue";

const props = defineProps<{
  rom: DetailedRom;
}>();

const walkthroughs = computed<Walkthrough[]>(
  () => (props.rom.walkthroughs || []) as Walkthrough[],
);

const selectedWalkthrough = ref<Walkthrough | null>(null);
const isModalOpen = ref(false);
const isLoading = ref(false);

const openWalkthrough = async (walkthrough: Walkthrough) => {
  isLoading.value = true;
  try {
    selectedWalkthrough.value = walkthrough;
    isModalOpen.value = true;
  } finally {
    isLoading.value = false;
  }
};

const closeModal = () => {
  isModalOpen.value = false;
  selectedWalkthrough.value = null;
};
</script>

<template>
  <div>
    <!-- Loading State -->
    <div v-if="isLoading" class="d-flex flex-column gap-3">
      <v-skeleton-loader v-for="i in 3" :key="i" type="card" class="mb-3" />
    </div>

    <!-- Empty State -->
    <v-alert
      v-else-if="!walkthroughs.length"
      type="info"
      variant="tonal"
      class="text-center"
    >
      <div class="d-flex flex-column align-center gap-3">
        <v-icon size="48" color="info">mdi-book-open-page-variant</v-icon>
        <div>
          <div class="text-h6 mb-2">No walkthroughs available</div>
          <div class="text-body-2">
            Add walkthroughs to help guide you through this game.
          </div>
        </div>
      </div>
    </v-alert>

    <!-- Walkthrough Cards -->
    <div v-else-if="walkthroughs.length" class="d-flex flex-column gap-3">
      <v-card
        v-for="wt in walkthroughs"
        :key="wt.id"
        class="cursor-pointer hover:bg-surface-variant transition-colors"
        elevation="2"
        tabindex="0"
        role="button"
        :aria-label="`Open walkthrough: ${wt.title || wt.url}`"
        @click="openWalkthrough(wt)"
        @keydown.enter="openWalkthrough(wt)"
        @keydown.space.prevent="openWalkthrough(wt)"
      >
        <v-card-text class="pa-4">
          <div class="d-flex align-center justify-between">
            <div class="d-flex align-center flex-grow-1">
              <v-chip size="small" class="mr-3" color="primary">
                {{ wt.source }}
              </v-chip>
              <div class="d-flex flex-column">
                <span class="text-body-1 font-weight-medium">
                  {{ wt.title?.split("by")[0] || wt.url }}
                </span>
                <div class="text-caption text-medium-emphasis">
                  <span v-if="wt.author">By {{ wt.author }}</span>
                  <span v-else>{{ wt.url }}</span>
                </div>
              </div>
            </div>

            <div class="d-flex align-center gap-2">
              <WalkthroughProgress :walkthrough="wt" />
              <v-btn
                icon="mdi-open-in-new"
                variant="text"
                size="small"
                :href="wt.url"
                target="_blank"
                @click.stop
              />
            </div>
          </div>
        </v-card-text>
      </v-card>
    </div>

    <WalkthroughModal
      v-if="selectedWalkthrough"
      :walkthrough="selectedWalkthrough"
      :is-open="isModalOpen"
      @close="closeModal"
    />
  </div>
</template>

<style scoped>
.cursor-pointer:focus {
  outline: 2px solid rgb(var(--v-theme-primary));
  outline-offset: 2px;
}
</style>
