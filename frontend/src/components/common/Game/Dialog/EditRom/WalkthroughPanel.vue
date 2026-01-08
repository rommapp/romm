<script setup lang="ts">
import type { Emitter } from "mitt";
import { computed, inject, onMounted, ref, watch } from "vue";
import { useDisplay } from "vuetify";
import {
  createWalkthroughForRom,
  deleteWalkthrough,
  fetchWalkthrough,
  listWalkthroughsForRom,
  uploadWalkthroughForRom,
  type StoredWalkthrough,
  type WalkthroughFormat,
} from "@/services/api/walkthrough";
import type { Events } from "@/types/emitter";
import { FRONTEND_RESOURCES_PATH } from "@/utils";

const props = defineProps<{
  romId: number;
  initialWalkthroughs?: StoredWalkthrough[];
}>();

const emitter = inject<Emitter<Events>>("emitter");
const { mdAndUp } = useDisplay();

const url = ref("");
const loading = ref(false);
const saving = ref(false);
const removingId = ref<number | null>(null);
const error = ref<string | null>(null);
const content = ref("");
const title = ref<string | null>(null);
const author = ref<string | null>(null);
const source = ref<string | null>(null);
const contentFormat = ref<WalkthroughFormat>("html");
const walkthroughs = ref<StoredWalkthrough[]>(props.initialWalkthroughs || []);
const savedOpenPanels = ref<number[]>([]);
const savedVisibleLines = ref<Record<number, number>>({});
const LINE_CHUNK = 300;
const SCROLL_THRESHOLD = 200;
const uploadFile = ref<File | null>(null);
const uploading = ref(false);

const hasResult = computed(
  () => !!content.value && !loading.value && !error.value,
);
const hasRom = computed(() => !!props.romId);

const isSavedOpen = (id: number) => savedOpenPanels.value.includes(id);
const asLines = (value: string) => value.split(/\r?\n/);
const savedLineCache = new Map<number, string[]>();
const getSavedLines = (wt: StoredWalkthrough) => {
  if (savedLineCache.has(wt.id)) return savedLineCache.get(wt.id)!;
  const lines = asLines(wt.content);
  savedLineCache.set(wt.id, lines);
  return lines;
};
const getVisibleSavedLines = (wt: StoredWalkthrough) => {
  const lines = getSavedLines(wt);
  const current =
    savedVisibleLines.value[wt.id] ?? Math.min(lines.length, LINE_CHUNK);
  savedVisibleLines.value[wt.id] = current;
  return lines.slice(0, current);
};
const canShowMoreSaved = (wt: StoredWalkthrough) =>
  (savedVisibleLines.value[wt.id] ?? LINE_CHUNK) < getSavedLines(wt).length;
const showMoreSaved = (wt: StoredWalkthrough) => {
  const total = getSavedLines(wt).length;
  const next = Math.min(
    (savedVisibleLines.value[wt.id] ?? LINE_CHUNK) + LINE_CHUNK,
    total,
  );
  savedVisibleLines.value[wt.id] = next;
};
const showAllSaved = (wt: StoredWalkthrough) => {
  savedVisibleLines.value[wt.id] = getSavedLines(wt).length;
};
const handleSavedScroll = (wt: StoredWalkthrough, event: Event) => {
  const target = event.target as HTMLElement;
  if (!target) return;
  const distanceToBottom =
    target.scrollHeight - (target.scrollTop + target.clientHeight);
  if (distanceToBottom < SCROLL_THRESHOLD && canShowMoreSaved(wt)) {
    showMoreSaved(wt);
  }
};

const pdfUrl = (wt: StoredWalkthrough) =>
  wt.file_path ? `${FRONTEND_RESOURCES_PATH}/${wt.file_path}` : "";

watch(
  () => props.initialWalkthroughs,
  (next) => {
    if (next) walkthroughs.value = next;
  },
);

watch(
  () => props.romId,
  () => {
    void loadWalkthroughs();
  },
);

async function loadWalkthroughs() {
  if (!hasRom.value) return;
  try {
    const { data } = await listWalkthroughsForRom(props.romId);
    walkthroughs.value = data;
  } catch (err) {
    console.error(err);
  }
}

onMounted(() => {
  void loadWalkthroughs();
});

async function runFetch() {
  if (!url.value) {
    emitter?.emit("snackbarShow", {
      msg: "Walkthrough URL is required",
      icon: "mdi-close-circle",
      color: "red",
    });
    return;
  }

  loading.value = true;
  error.value = null;
  content.value = "";
  title.value = null;
  author.value = null;
  source.value = null;

  try {
    const { data } = await fetchWalkthrough({
      url: url.value.trim(),
    });
    content.value = data.content;
    contentFormat.value = data.format;
    source.value = data.source;
    title.value = data.title ?? null;
    author.value = data.author ?? null;
  } catch (err: any) {
    const detail =
      err?.response?.data?.detail ||
      err?.message ||
      "Failed to fetch walkthrough. Please verify the URL.";
    error.value = detail;
    emitter?.emit("snackbarShow", {
      msg: detail,
      icon: "mdi-close-circle",
      color: "red",
      timeout: 4000,
    });
  } finally {
    loading.value = false;
  }
}

async function saveToRom() {
  if (!hasRom.value) return;
  if (!url.value) {
    emitter?.emit("snackbarShow", {
      msg: "Walkthrough URL is required",
      icon: "mdi-close-circle",
      color: "red",
    });
    return;
  }
  saving.value = true;
  try {
    await createWalkthroughForRom({
      romId: props.romId,
      url: url.value.trim(),
    });
    await loadWalkthroughs();
    emitter?.emit("snackbarShow", {
      msg: "Walkthrough added to ROM",
      icon: "mdi-check-bold",
      color: "green",
    });
  } catch (err: any) {
    const detail =
      err?.response?.data?.detail ||
      err?.message ||
      "Failed to add walkthrough to ROM.";
    emitter?.emit("snackbarShow", {
      msg: detail,
      icon: "mdi-close-circle",
      color: "red",
    });
  } finally {
    saving.value = false;
  }
}

async function uploadFileToRom() {
  if (!hasRom.value) return;
  if (!uploadFile.value) {
    emitter?.emit("snackbarShow", {
      msg: "Choose a walkthrough file (PDF, HTML, or TXT)",
      icon: "mdi-close-circle",
      color: "red",
    });
    return;
  }

  uploading.value = true;
  try {
    await uploadWalkthroughForRom({
      romId: props.romId,
      file: uploadFile.value,
      title: title.value || undefined,
      author: author.value || undefined,
    });
    uploadFile.value = null;
    await loadWalkthroughs();
    emitter?.emit("snackbarShow", {
      msg: "Walkthrough uploaded",
      icon: "mdi-check-bold",
      color: "green",
    });
  } catch (err: any) {
    const detail =
      err?.response?.data?.detail ||
      err?.message ||
      "Failed to upload walkthrough.";
    emitter?.emit("snackbarShow", {
      msg: detail,
      icon: "mdi-close-circle",
      color: "red",
    });
  } finally {
    uploading.value = false;
  }
}

async function removeSavedWalkthrough(id: number) {
  removingId.value = id;
  try {
    await deleteWalkthrough(id);
    walkthroughs.value = walkthroughs.value.filter((w) => w.id !== id);
    emitter?.emit("snackbarShow", {
      msg: "Walkthrough removed",
      icon: "mdi-check-bold",
      color: "green",
    });
  } catch (err: any) {
    const detail =
      err?.response?.data?.detail ||
      err?.message ||
      "Failed to remove walkthrough.";
    emitter?.emit("snackbarShow", {
      msg: detail,
      icon: "mdi-close-circle",
      color: "red",
    });
  } finally {
    removingId.value = null;
  }
}
</script>

<template>
  <v-expansion-panel elevation="0">
    <v-expansion-panel-title class="bg-toplayer">
      <v-icon class="mr-2"> mdi-file-document-outline </v-icon>
      Walkthrough
    </v-expansion-panel-title>
    <v-expansion-panel-text class="mt-4 px-2">
      <v-row no-gutters class="mb-3" :class="{ 'flex-column': !mdAndUp }">
        <v-col class="pa-2" :cols="mdAndUp ? 10 : 12">
          <v-text-field
            v-model="url"
            label="Walkthrough URL (GameFAQs)"
            placeholder="https://gamefaqs.gamespot.com/.../faqs/..."
            variant="outlined"
            clearable
          />
        </v-col>
        <v-col class="px-2 d-flex align-center" :cols="mdAndUp ? 2 : 12">
          <v-btn
            color="primary"
            class="bg-toplayer"
            variant="flat"
            :loading="loading"
            block
            @click="runFetch"
          >
            Fetch
          </v-btn>
        </v-col>
      </v-row>

      <v-alert
        v-if="error"
        type="error"
        density="comfortable"
        class="mb-3"
        :text="error"
      />

      <v-skeleton-loader
        v-if="loading"
        type="paragraph, paragraph, paragraph"
        class="mt-2"
      />

      <div v-else-if="hasResult" class="bg-toplayer rounded pa-3 border">
        <div class="d-flex align-start justify-space-between mb-3 flex-wrap">
          <div class="text-body-2">
            <div>
              Source: <strong>{{ source }}</strong> • Format:
              <strong>{{ contentFormat.toUpperCase() }}</strong>
            </div>
            <div
              v-if="title || author"
              class="text-caption text-medium-emphasis mt-1"
            >
              <span v-if="title">{{ title }}</span>
              <span v-if="author">
                {{ title ? " • " : "" }}by {{ author }}
              </span>
            </div>
          </div>
          <v-chip size="small" color="primary" variant="tonal">
            Preview
          </v-chip>
        </div>

        <div class="max-h-96 overflow-y-auto">
          <div
            v-if="contentFormat === 'html'"
            class="walkthrough-html"
            v-html="content"
          />
          <pre v-else class="walkthrough-text">{{ content }}</pre>
        </div>
        <div class="flex items-center justify-between">
          <v-btn
            class="mt-3"
            :href="url"
            target="_blank"
            color="primary"
            variant="outlined"
          >
            Open Walkthrough in Browser
          </v-btn>
          <v-btn
            class="mt-3"
            color="primary"
            variant="flat"
            :loading="saving"
            @click="saveToRom"
          >
            Add Walkthrough to Rom
          </v-btn>
        </div>
      </div>

      <v-divider class="my-4" />

      <div class="bg-toplayer rounded pa-3 border mb-4">
        <div class="d-flex align-center justify-space-between mb-3">
          <div>
            <div class="text-subtitle-2 font-weight-medium">
              Upload Walkthrough File
            </div>
            <div class="text-caption text-medium-emphasis">
              PDF, HTML, or TXT supported.
            </div>
          </div>
          <v-btn
            color="primary"
            variant="flat"
            :loading="uploading"
            :disabled="!uploadFile"
            @click="uploadFileToRom"
          >
            Upload
          </v-btn>
        </div>
        <v-file-input
          v-model="uploadFile"
          accept=".pdf,.html,.htm,.txt,.md"
          variant="outlined"
          prepend-icon="mdi-file-upload"
          label="Select walkthrough file"
          show-size
        />
      </div>

      <div class="d-flex align-center justify-space-between mb-2">
        <h4 class="text-subtitle-1 font-weight-bold">Saved Walkthroughs</h4>
        <v-chip
          size="small"
          color="primary"
          variant="tonal"
          class="text-caption"
        >
          {{ walkthroughs.length }} saved
        </v-chip>
      </div>

      <v-alert
        v-if="!walkthroughs.length"
        type="info"
        variant="tonal"
        class="my-2"
        text="No walkthroughs saved for this ROM yet."
      />

      <v-expansion-panels v-else v-model="savedOpenPanels" multiple>
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
                  <span v-if="wt.author"> By {{ wt.author }} </span>
                  <span v-else>{{ wt.url }}</span>
                </div>
              </div>
            </div>
            <template #actions>
              <v-btn
                icon="mdi-open-in-new"
                variant="text"
                size="small"
                :href="wt.url"
                target="_blank"
                class="mr-1"
              />
              <v-btn
                icon="mdi-delete"
                variant="text"
                size="small"
                :loading="removingId === wt.id"
                @click.stop="removeSavedWalkthrough(wt.id)"
              />
            </template>
          </v-expansion-panel-title>
          <v-expansion-panel-text>
            <div v-if="isSavedOpen(wt.id)">
              <div
                v-if="wt.format === 'html'"
                class="walkthrough-html"
                v-html="wt.content"
              />
              <div v-else-if="wt.format === 'pdf'">
                <div class="d-flex align-center justify-space-between mb-2">
                  <div class="text-body-2">PDF walkthrough</div>
                  <v-btn
                    size="small"
                    color="primary"
                    variant="tonal"
                    :href="pdfUrl(wt)"
                    target="_blank"
                  >
                    Open PDF
                  </v-btn>
                </div>
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
                @scroll.passive="handleSavedScroll(wt, $event)"
              >
                <div
                  v-for="(line, idx) in getVisibleSavedLines(wt)"
                  :key="idx"
                  class="walkthrough-line"
                >
                  {{ line }}
                </div>
                <div v-if="canShowMoreSaved(wt)" class="d-flex justify-end">
                  <v-btn
                    size="x-small"
                    variant="text"
                    @click="showAllSaved(wt)"
                  >
                    Show all
                  </v-btn>
                </div>
              </div>
            </div>
            <v-skeleton-loader v-else type="paragraph" class="my-2" />
          </v-expansion-panel-text>
        </v-expansion-panel>
      </v-expansion-panels>
    </v-expansion-panel-text>
  </v-expansion-panel>
</template>

<style scoped>
.walkthrough-text {
  background: #0f1115;
  color: #e5e7eb;
  padding: 12px;
  border-radius: 8px;
  white-space: pre-wrap;
}

.walkthrough-html {
  background: #0f1115;
  color: #e5e7eb;
  padding: 12px;
  border-radius: 8px;
  max-height: 360px;
  overflow-y: auto;
}

.walkthrough-virtual {
  background: #0f1115;
  border-radius: 8px;
  padding: 8px;
  max-height: 360px;
  overflow-y: auto;
}

.walkthrough-iframe {
  width: 100%;
  height: 360px;
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
