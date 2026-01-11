<script setup lang="ts">
import { computed, ref } from "vue";
import { useWalkThrough } from "@/composables/useWalkThrough";
import type { Walkthrough } from "@/composables/useWalkThrough";
import type { DetailedRom } from "@/stores/roms";

const props = defineProps<{
  rom: DetailedRom;
}>();

const walkthroughs = computed<Walkthrough[]>(
  () => (props.rom.walkthroughs || []) as Walkthrough[],
);

const openPanels = ref<number[]>([]);
const {
  handleScroll,
  storeHtmlProgress,
  progressLabel,
  getVisibleText,
  canShowMore,
  showAll,
  pdfUrl,
  setContentRef,
} = useWalkThrough({ openPanels });

const isOpen = (id: number) => openPanels.value.includes(id);
</script>

<template>
  <v-alert
    v-if="!walkthroughs.length"
    type="info"
    variant="tonal"
    text="No walkthroughs saved for this ROM."
  />
  <v-expansion-panels v-else v-model="openPanels" multiple>
    <v-expansion-panel
      v-for="wt in walkthroughs"
      :key="wt.id"
      :value="wt.id"
      elevation="0"
    >
      <v-expansion-panel-title class="bg-toplayer">
        <div class="d-flex align-center">
          <v-chip size="small" class="mr-2" color="primary">
            {{ wt.source }}
          </v-chip>
          <div class="d-flex flex-column">
            <div class="text-body-2 font-weight-medium">
              {{ wt.title || wt.url }}
            </div>
            <div class="text-caption text-medium-emphasis">
              <span v-if="wt.author">By {{ wt.author }}</span>
              <span v-else>{{ wt.url }}</span>
            </div>
          </div>
        </div>
        <v-chip size="x-small" color="primary" variant="tonal" class="ml-2">
          {{ progressLabel(wt) }}
        </v-chip>
        <template #actions>
          <v-btn
            icon="mdi-open-in-new"
            variant="text"
            size="small"
            :href="wt.url"
            target="_blank"
            class="mr-1"
          />
        </template>
      </v-expansion-panel-title>
      <v-expansion-panel-text>
        <div v-if="isOpen(wt.id)">
          <div
            v-if="wt.format === 'html'"
            class="overflow-auto rounded-lg min-h-[420px] p-4"
            v-html="wt.content"
            :ref="(el) => setContentRef(wt.id, el as HTMLElement | null)"
            @scroll.passive="(e) => storeHtmlProgress(wt, e)"
          />
          <div v-else-if="wt.format === 'pdf'" class="walkthrough-pdf">
            <iframe
              v-if="pdfUrl(wt)"
              :src="pdfUrl(wt)"
              class="w-full min-h-[600px] rounded-lg mt-4"
              title="Walkthrough PDF"
            />
            <div v-else class="text-caption text-medium-emphasis">
              PDF file missing
            </div>
          </div>
          <div
            v-else
            class="walkthrough-virtual"
            @scroll.passive="handleScroll(wt, $event)"
            :ref="(el) => setContentRef(wt.id, el as HTMLElement | null)"
          >
            <div
              v-for="(line, idx) in getVisibleText(wt)"
              :key="idx"
              :class="{
                'whitespace-pre-wrap': wt.source === 'UPLOAD',
                'whitespace-pre': wt.source !== 'UPLOAD',
              }"
              class="break-after-all font-mono leading-5 overflow-x-auto"
            >
              {{ line || "\u00A0" }}
            </div>
            <div v-if="canShowMore(wt)" class="d-flex justify-end">
              <v-btn size="x-small" variant="text" @click="showAll(wt)">
                Show all
              </v-btn>
            </div>
          </div>
        </div>
        <v-skeleton-loader v-else type="paragraph" class="my-2" />
      </v-expansion-panel-text>
    </v-expansion-panel>
  </v-expansion-panels>
</template>
