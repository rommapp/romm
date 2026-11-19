<script setup lang="ts">
// MameMatchDialog: matches an arcade platform's games against the loaded
// MAME index by set name, or removes their MAME data. It runs apart from
// scans on purpose: only an admin who starts it here gets MAME titles,
// parent/clone grouping and filters.
import { computed, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { MameMatchPayload } from "@/__generated__";
import PlatformIcon from "@/components/shared/PlatformIcon.vue";
import { useSnackbar } from "@/composables/useSnackbar";
import {
  RAlert,
  RBtn,
  RDialog,
  RProgressLinear,
  RSegmentedControl,
  RSwitch,
} from "@/lib";
import mameApi from "@/services/api/mame";
import taskApi from "@/services/api/task";
import storeGalleryRoms from "@/stores/galleryRoms";
import type { Platform } from "@/stores/platforms";
import { errorMessage } from "@/utils/errorMessage";

type Action = NonNullable<MameMatchPayload["action"]>;

const POLL_MS = 1500;
const DONE = new Set(["finished", "failed", "stopped", "canceled"]);

const props = defineProps<{
  modelValue: boolean;
  platform: Platform;
}>();

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
}>();

const { t } = useI18n();
const snackbar = useSnackbar();
const galleryRoms = storeGalleryRoms();

const indexLoaded = ref<boolean | null>(null);
const action = ref<Action>("match");
const rename = ref(true);
const taskId = ref<string | null>(null);
const progress = ref<{ processed: number; total: number } | null>(null);
let pollTimer: ReturnType<typeof setTimeout> | undefined;

const running = computed(() => taskId.value !== null);

const actionItems = computed(() => [
  { id: "match" as Action, label: t("platform.mame-match-action-match") },
  { id: "clear" as Action, label: t("platform.mame-match-action-clear") },
]);

const percent = computed(() =>
  progress.value && progress.value.total > 0
    ? (100 * progress.value.processed) / progress.value.total
    : 0,
);

async function loadStatus() {
  try {
    indexLoaded.value = (await mameApi.getIndexStatus()).loaded;
  } catch {
    indexLoaded.value = null;
  }
}

watch(
  () => props.modelValue,
  (open) => {
    if (open && !running.value) void loadStatus();
  },
  { immediate: true },
);

function close() {
  emit("update:modelValue", false);
}

function finish(status: string) {
  taskId.value = null;
  progress.value = null;
  if (status === "finished") {
    snackbar.success(t("platform.mame-match-done"), {
      icon: "mdi-check-bold",
    });
  } else {
    snackbar.error(t("platform.mame-match-failed", { detail: status }), {
      icon: "mdi-close-circle",
    });
  }
  galleryRoms.invalidateWindows();
  void galleryRoms.fetchInitialMetadata();
  close();
}

async function poll() {
  const id = taskId.value;
  if (!id) return;
  try {
    const { data } = await taskApi.getTaskById(id);
    const meta = data.meta as {
      update_stats?: { processed: number; total: number } | null;
    };
    progress.value = meta.update_stats ?? progress.value;
    if (DONE.has(data.status)) {
      finish(data.status);
      return;
    }
  } catch {
    // A missed poll is retried on the next tick.
  }
  pollTimer = setTimeout(() => void poll(), POLL_MS);
}

async function start() {
  try {
    const job = await mameApi.matchPlatform({
      platform_id: props.platform.id,
      action: action.value,
      rename: rename.value,
    });
    taskId.value = job.task_id;
    progress.value = { processed: 0, total: props.platform.rom_count ?? 0 };
    pollTimer = setTimeout(() => void poll(), POLL_MS);
  } catch (err) {
    snackbar.error(
      t("platform.mame-match-failed", { detail: errorMessage(err) }),
      { icon: "mdi-close-circle" },
    );
  }
}

onBeforeUnmount(() => clearTimeout(pollTimer));
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-slot-machine-outline"
    :width="520"
    cancelable
    @update:model-value="$emit('update:modelValue', $event)"
    @close="close"
  >
    <template #header>
      <span>{{ t("platform.mame-match") }}</span>
    </template>

    <template #content>
      <div class="r-mame-match">
        <div class="r-mame-match__head">
          <PlatformIcon
            :slug="platform.slug"
            :fs-slug="platform.fs_slug"
            :alt="platform.display_name"
            :size="40"
          />
          <div class="r-mame-match__meta">
            <p class="r-mame-match__name">{{ platform.display_name }}</p>
            <p class="r-mame-match__count">
              {{ t("platform.rom-count", { n: platform.rom_count ?? 0 }) }}
            </p>
          </div>
        </div>

        <p class="r-mame-match__intro">{{ t("platform.mame-match-intro") }}</p>

        <template v-if="running">
          <p class="r-mame-match__progress" data-testid="mame-match-progress">
            {{
              t("platform.mame-match-running", {
                processed: progress?.processed ?? 0,
                total: progress?.total ?? 0,
              })
            }}
          </p>
          <RProgressLinear
            :model-value="percent"
            :indeterminate="!progress?.total"
            :aria-label="t('platform.mame-match')"
          />
        </template>

        <template v-else>
          <RSegmentedControl
            v-model="action"
            :items="actionItems"
            :aria-label="t('platform.mame-match')"
          />

          <template v-if="action === 'match'">
            <RAlert
              v-if="indexLoaded === false"
              type="info"
              density="compact"
              :icon="false"
            >
              {{ t("platform.mame-match-no-index") }}
            </RAlert>
            <RSwitch v-model="rename" :label="t('platform.mame-match-rename')" />
          </template>
          <p v-else class="r-mame-match__note">
            {{ t("platform.mame-match-clear-note") }}
          </p>
        </template>
      </div>
    </template>

    <template #footer>
      <RBtn
        variant="translucent"
        color="primary"
        :prepend-icon="action === 'clear' ? 'mdi-delete-outline' : 'mdi-play'"
        :disabled="running"
        :loading="running"
        @click="start"
      >
        {{ t("platform.mame-match-start") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-mame-match {
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.r-mame-match__head {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  background: var(--r-color-bg-elevated);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-md);
}
.r-mame-match__meta {
  min-width: 0;
  flex: 1;
}
.r-mame-match__name {
  margin: 0;
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.r-mame-match__count {
  margin: 2px 0 0;
  font-size: 11px;
  color: var(--r-color-fg-muted);
}
.r-mame-match__intro,
.r-mame-match__note {
  margin: 0;
  font-size: 13px;
  color: var(--r-color-fg-muted);
}
.r-mame-match__progress {
  margin: 0;
  font-variant-numeric: tabular-nums;
}
</style>
