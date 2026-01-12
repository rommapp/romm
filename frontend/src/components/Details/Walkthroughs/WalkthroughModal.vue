<script setup lang="ts">
import { ref, computed } from "vue";
import { useWalkthrough } from "@/composables/useWalkthrough";
import type { Walkthrough } from "@/composables/useWalkthrough";
import WalkthroughProgress from "./WalkthroughProgress.vue";

const props = defineProps<{
  walkthrough: Walkthrough;
  isOpen: boolean;
}>();

const emit = defineEmits<{
  close: [];
}>();

const isFullscreen = ref(false);
const fontSize = ref(14);
const searchQuery = ref("");

const fontSizes = [
  { label: "Small", value: 12 },
  { label: "Medium", value: 14 },
  { label: "Large", value: 16 },
  { label: "Extra Large", value: 18 },
];

const modalClass = computed(() => ({
  "fullscreen-modal": isFullscreen.value,
}));

const modalMaxWidth = computed(() => (isFullscreen.value ? "100vw" : "90vw"));
const modalMaxHeight = computed(() => (isFullscreen.value ? "100vh" : "90vh"));

const openPanels = ref<number[]>([]);
const {
  handleScroll,
  storeHtmlProgress,
  getVisibleText,
  getPdfUrl,
  setContentRef,
} = useWalkthrough({ openPanels });

const handleClose = () => emit("close");

const toggleFullscreen = () => {
  isFullscreen.value = !isFullscreen.value;
};

const increaseFontSize = () => {
  const currentIndex = fontSizes.findIndex((f) => f.value === fontSize.value);
  if (currentIndex < fontSizes.length - 1) {
    fontSize.value = fontSizes[currentIndex + 1].value;
  }
};

const decreaseFontSize = () => {
  const currentIndex = fontSizes.findIndex((f) => f.value === fontSize.value);
  if (currentIndex > 0) {
    fontSize.value = fontSizes[currentIndex - 1].value;
  }
};

const textStyle = computed(() => ({
  fontSize: `${fontSize.value}px`,
  lineHeight: `${fontSize.value * 1.4}px`,
  fontFamily: "ui-monospace, SFMono-Regular, monospace",
}));

console.log(props.walkthrough);
</script>

<template>
  <v-dialog
    :model-value="isOpen"
    :max-width="modalMaxWidth"
    :max-height="modalMaxHeight"
    :class="modalClass"
    scrollable
    @update:model-value="!$event && handleClose()"
    @keydown.esc="handleClose"
  >
    <v-card class="h-100 d-flex flex-column">
      <v-card-title class="d-flex align-center justify-between pa-4 bg-surface">
        <div class="d-flex align-center">
          <v-chip size="small" class="mr-3" color="primary">
            {{ walkthrough.source }}
          </v-chip>
          <div class="d-flex flex-column">
            <span class="text-h6 font-weight-medium">
              {{ walkthrough.title?.split("by")[0] || walkthrough.url }}
            </span>
            <div class="text-caption text-medium-emphasis">
              <span v-if="walkthrough.author">By {{ walkthrough.author }}</span>
              <span v-else>{{ walkthrough.url }}</span>
            </div>
          </div>
        </div>

        <div class="d-flex align-center gap-1">
          <WalkthroughProgress :walkthrough="walkthrough" />

          <!-- Text Controls (only for text format) -->
          <template v-if="walkthrough.format === 'text'">
            <v-divider vertical class="mx-2" />
            <v-btn-group variant="outlined" size="small">
              <v-btn
                icon="mdi-format-font-size-decrease"
                size="small"
                :disabled="fontSize <= fontSizes[0].value"
                @click="decreaseFontSize"
              />
              <v-btn
                icon="mdi-format-font-size-increase"
                size="small"
                :disabled="fontSize >= fontSizes[fontSizes.length - 1].value"
                @click="increaseFontSize"
              />
            </v-btn-group>
          </template>

          <v-divider vertical class="mx-2" />

          <v-btn
            :icon="isFullscreen ? 'mdi-fullscreen-exit' : 'mdi-fullscreen'"
            variant="text"
            size="small"
            @click="toggleFullscreen"
          />
          <v-btn
            v-if="walkthrough.format !== 'html'"
            icon="mdi-open-in-new"
            variant="text"
            size="small"
            :href="
              walkthrough.format === 'pdf'
                ? getPdfUrl(walkthrough)
                : walkthrough.url
            "
            target="_blank"
          />
          <v-btn
            icon="mdi-close"
            variant="text"
            size="small"
            @click="handleClose"
          />
        </div>
      </v-card-title>

      <v-divider />

      <!-- Search Bar (for text content only) -->
      <v-toolbar
        v-if="walkthrough.format === 'text'"
        density="compact"
        flat
        class="border-b"
      >
        <v-text-field
          v-model="searchQuery"
          prepend-inner-icon="mdi-magnify"
          placeholder="Search in walkthrough..."
          variant="outlined"
          density="compact"
          hide-details
          clearable
          class="mx-4"
        />
      </v-toolbar>

      <v-card-text class="pa-0 flex-grow-1 overflow-hidden">
        <!-- HTML Content -->
        <div v-if="walkthrough.format === 'html'" class="h-100">
          <div
            v-if="walkthrough.content && walkthrough.content.trim()"
            :ref="
              (el) => setContentRef(walkthrough.id, el as HTMLElement | null)
            "
            class="overflow-auto pa-6 h-100 bg-surface font-mono whitespace-pre-wrap leading-5"
            style="max-height: 70vh"
            @scroll.passive="(e) => storeHtmlProgress(walkthrough, e)"
            v-html="walkthrough.content"
          />
        </div>

        <!-- PDF Content -->
        <div v-else-if="walkthrough.format === 'pdf'" class="h-100">
          <div v-if="getPdfUrl(walkthrough)" class="h-100 d-flex flex-column">
            <object
              :data="getPdfUrl(walkthrough)"
              type="application/pdf"
              class="w-full flex-grow-1"
              style="min-height: 60vh; border: none"
            >
              <div class="pa-4 text-center">
                <v-alert type="info" variant="tonal">
                  <div class="mb-2">
                    Your browser cannot display PDFs inline.
                  </div>
                  <v-btn
                    :href="getPdfUrl(walkthrough)"
                    target="_blank"
                    variant="elevated"
                    color="primary"
                  >
                    <v-icon start>mdi-open-in-new</v-icon>
                    Open PDF
                  </v-btn>
                </v-alert>
              </div>
            </object>
          </div>
          <div v-else class="pa-6 text-center">
            <v-alert type="warning" variant="tonal">
              PDF file is missing or could not be loaded.
            </v-alert>
          </div>
        </div>

        <!-- Text Content -->
        <div
          v-else
          :ref="(el) => setContentRef(walkthrough.id, el as HTMLElement | null)"
          class="overflow-auto pa-6 h-100"
          :style="{ maxHeight: isFullscreen ? '100vh' : '70vh' }"
          @scroll.passive="handleScroll(walkthrough, $event)"
        >
          <div
            v-for="(line, idx) in getVisibleText(walkthrough)"
            :key="idx"
            :class="{
              'search-highlight':
                searchQuery &&
                line.toLowerCase().includes(searchQuery.toLowerCase()),
            }"
            class="mb-4 overflow-x-auto"
            :style="textStyle"
          >
            {{ line || "\u00A0" }}
          </div>
        </div>
      </v-card-text>
    </v-card>
  </v-dialog>
</template>

<style scoped>
.fullscreen-modal :deep(.v-dialog) {
  margin: 0;
  max-width: 100vw !important;
  max-height: 100vh !important;
  height: 100vh;
  width: 100vw;
}

/* Search highlighting */
.search-highlight {
  background-color: rgba(var(--v-theme-warning), 0.3);
  padding: 0 2px;
  border-radius: 2px;
}

/* Better text selection */
::selection {
  background: rgba(var(--v-theme-primary), 0.3);
}
</style>
