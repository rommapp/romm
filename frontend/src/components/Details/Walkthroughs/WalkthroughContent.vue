<script setup lang="ts">
import { ref } from "vue";
import { useWalkthrough } from "@/composables/useWalkthrough";
import type { Walkthrough } from "@/composables/useWalkthrough";

defineProps<{
  walkthrough: Walkthrough;
  isOpen: (id: number) => boolean;
}>();

const openPanels = ref<number[]>([]);
const {
  handleScroll,
  storeHtmlProgress,
  getVisibleText,
  canShowMore,
  showAll,
  getPdfUrl,
  setContentRef,
} = useWalkthrough({ openPanels });
</script>
<template>
  <v-expansion-panel-text>
    <div v-if="isOpen(walkthrough.id)">
      <div
        v-if="walkthrough.format === 'html'"
        :ref="(el) => setContentRef(walkthrough.id, el as HTMLElement | null)"
        class="overflow-auto rounded-lg min-h-[420px] pa-4"
        @scroll.passive="(e) => storeHtmlProgress(walkthrough, e)"
        v-html="walkthrough.content"
      />
      <div v-else-if="walkthrough.format === 'pdf'">
        <iframe
          v-if="getPdfUrl(walkthrough)"
          :src="getPdfUrl(walkthrough)"
          class="w-full min-h-[600px] rounded-lg mt-4"
          title="Walkthrough PDF"
        />
        <div v-else class="text-caption text-medium-emphasis">
          PDF file missing
        </div>
      </div>
      <div
        v-else
        :ref="(el) => setContentRef(walkthrough.id, el as HTMLElement | null)"
        class="overflow-auto rounded-lg min-h-[420px] pa-4"
        @scroll.passive="handleScroll(walkthrough, $event)"
      >
        <div
          v-for="(line, idx) in getVisibleText(walkthrough)"
          :key="idx"
          :class="{
            'whitespace-pre-wrap': walkthrough.source === 'UPLOAD',
            'whitespace-pre': walkthrough.source !== 'UPLOAD',
          }"
          class="break-after-all font-mono leading-5 overflow-x-auto"
        >
          {{ line || "\u00A0" }}
        </div>
        <div v-if="canShowMore(walkthrough)" class="d-flex justify-end">
          <v-btn size="x-small" variant="text" @click="showAll(walkthrough)">
            Show all
          </v-btn>
        </div>
      </div>
    </div>
    <v-skeleton-loader v-else type="paragraph" class="my-2" />
  </v-expansion-panel-text>
</template>
