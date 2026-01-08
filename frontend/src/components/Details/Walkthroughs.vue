<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import { computed, nextTick, ref, watch } from "vue";
import type { DetailedRom } from "@/stores/roms";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

const props = defineProps<{
  rom: DetailedRom;
}>();

const openPanels = ref<number[]>([]);
const visibleLines = ref<Record<number, number>>({});
const LINE_CHUNK = 400;
const SCROLL_THRESHOLD = 200;
const contentRefs = new Map<number, HTMLElement>();
const storedProgress = useLocalStorage<
  Record<number, { lines?: number; scroll?: number; percent?: number }>
>("walkthrough.progress", {});
type Walkthrough = {
  id: number;
  url: string;
  title?: string | null;
  author?: string | null;
  source: string;
  format: "html" | "text" | "pdf";
  file_path?: string | null;
  content: string;
};
const walkthroughs = computed<Walkthrough[]>(
  () => (props.rom.walkthroughs || []) as Walkthrough[],
);

const lineCache = new Map<number, string[]>();

const isOpen = (id: number) => openPanels.value.includes(id);
const getLines = (wt: Walkthrough) => {
  if (lineCache.has(wt.id)) return lineCache.get(wt.id)!;
  const lines = wt.content ? wt.content.split(/\r?\n/) : [];
  lineCache.set(wt.id, lines);
  return lines;
};
const getVisibleText = (wt: Walkthrough) => {
  const lines = getLines(wt);
  const saved = storedProgress.value[wt.id]?.lines;
  const current =
    visibleLines.value[wt.id] ?? saved ?? Math.min(lines.length, LINE_CHUNK);
  visibleLines.value[wt.id] = current;
  return lines.slice(0, current);
};
const canShowMore = (wt: Walkthrough) =>
  (visibleLines.value[wt.id] ?? LINE_CHUNK) < getLines(wt).length;
const showMore = (wt: Walkthrough) => {
  const total = getLines(wt).length;
  const next = Math.min(
    (visibleLines.value[wt.id] ?? LINE_CHUNK) + LINE_CHUNK,
    total,
  );
  visibleLines.value[wt.id] = next;
};
const showAll = (wt: Walkthrough) => {
  visibleLines.value[wt.id] = getLines(wt).length;
};
const handleScroll = (wt: Walkthrough, event: Event) => {
  const target = event.target as HTMLElement;
  if (!target) return;
  const distanceToBottom =
    target.scrollHeight - (target.scrollTop + target.clientHeight);
  if (distanceToBottom < SCROLL_THRESHOLD && canShowMore(wt)) {
    showMore(wt);
  }

  storedProgress.value = {
    ...storedProgress.value,
    [wt.id]: {
      lines: visibleLines.value[wt.id] ?? LINE_CHUNK,
      scroll: target.scrollTop,
      percent: progressPercent(wt),
    },
  };
};

const pdfUrl = (wt: Walkthrough) =>
  wt.file_path ? `${FRONTEND_RESOURCES_PATH}/${wt.file_path}` : "";

const setContentRef = (id: number, el: HTMLElement | null) => {
  if (el) contentRefs.set(id, el);
  else contentRefs.delete(id);
};

const progressPercent = (wt: Walkthrough) => {
  if (wt.format === "text") {
    const total = getLines(wt).length || 1;
    const current = visibleLines.value[wt.id] ?? 0;
    return Math.min(100, Math.round((current / total) * 100));
  }
  if (wt.format === "html") {
    return storedProgress.value[wt.id]?.percent ?? 0;
  }
  return storedProgress.value[wt.id]?.percent ?? 0;
};

const progressLabel = (wt: Walkthrough) => {
  const pct = progressPercent(wt);
  return pct >= 99 ? "Completed" : `${pct}% read`;
};

const storeHtmlProgress = (wt: Walkthrough, event: Event) => {
  const target = event.target as HTMLElement;
  if (!target) return;
  const percent = Math.min(
    100,
    Math.round(
      ((target.scrollTop + target.clientHeight) / target.scrollHeight) * 100,
    ),
  );
  storedProgress.value = {
    ...storedProgress.value,
    [wt.id]: {
      ...storedProgress.value[wt.id],
      percent,
      scroll: target.scrollTop,
    },
  };
};

watch(
  () => openPanels.value.slice(),
  async (panels) => {
    await nextTick();
    panels.forEach((id) => {
      const saved = storedProgress.value[id];
      const el = contentRefs.get(id);
      if (saved?.scroll != null && el) {
        el.scrollTop = saved.scroll;
      }
    });
  },
);
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
            class="walkthrough-html"
            v-html="wt.content"
            :ref="(el) => setContentRef(wt.id, el as HTMLElement | null)"
            @scroll.passive="(e) => storeHtmlProgress(wt, e)"
          />
          <div v-else-if="wt.format === 'pdf'" class="walkthrough-pdf">
            <iframe
              v-if="pdfUrl(wt)"
              :src="pdfUrl(wt)"
              class="walkthrough-iframe"
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
              class="walkthrough-line break-after-all"
            >
              {{ line }}
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

<style scoped>
.walkthrough-html {
  background: #0f1115;
  color: #e5e7eb;
  padding: 12px;
  border-radius: 8px;
  max-height: 420px;
  overflow-y: auto;
}

.walkthrough-text {
  background: #0f1115;
  color: #e5e7eb;
  padding: 12px;
  border-radius: 8px;
  white-space: pre-wrap;
}

.walkthrough-virtual {
  background: #0f1115;
  border-radius: 8px;
  padding: 8px;
  max-height: 420px;
  overflow-y: auto;
}

.walkthrough-pdf {
  background: #0f1115;
  color: #e5e7eb;
  padding: 12px;
  border-radius: 8px;
}

.walkthrough-iframe {
  width: 100%;
  height: 420px;
  border: 1px solid rgba(255, 255, 255, 0.05);
  border-radius: 8px;
}

.walkthrough-line {
  color: #e5e7eb;
  font-family:
    "SFMono-Regular", Menlo, Monaco, Consolas, "Liberation Mono", "Courier New",
    monospace;
  white-space: pre;
  line-height: 1.35;
  overflow-x: auto;
}
</style>
