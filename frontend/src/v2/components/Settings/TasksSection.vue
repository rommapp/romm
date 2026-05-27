<script setup lang="ts">
// TasksSection — v2-native rebuild of v1
// `Settings/Administration/Tasks.vue`. Renders the watcher / scheduled /
// manual task lists and a "task history" feed below them. Each task
// list follows the mock's settings-task-row pattern (icon + info + run
// button) inside a 2-column grid. Sub-headings split each cluster.
//
// Polls `tasksStore.fetchTaskStatus` every 5s while mounted so the
// history feed updates in real time. Manual + scheduled tasks expose a
// run button that posts to /tasks/{name}/run.
import { RBtn, RIcon, RSpinner } from "@v2/lib";
import { storeToRefs } from "pinia";
import { computed, onMounted, onUnmounted } from "vue";
import { useI18n } from "vue-i18n";
import taskApi from "@/services/api/task";
import storeTasks from "@/stores/tasks";
import { convertCronExperssion, formatTimestamp } from "@/utils";
import { TaskStatusItem, type TaskStatusResponse } from "@/utils/tasks";
import SettingsSection from "@/v2/components/Settings/SettingsSection.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

defineOptions({ inheritAttrs: false });

const { t, locale } = useI18n();
const tasksStore = storeTasks();
const { watcherTasks, scheduledTasks, manualTasks, taskStatuses } =
  storeToRefs(tasksStore);
const snackbar = useSnackbar();

const watcherTasksUI = computed(() =>
  watcherTasks.value.map((task) => ({
    ...task,
    icon: task.enabled ? "mdi-file-check-outline" : "mdi-file-remove-outline",
  })),
);

const scheduledTasksUI = computed(() =>
  scheduledTasks.value.map((task) => ({
    ...task,
    icon: task.enabled ? "mdi-clock-check-outline" : "mdi-clock-remove-outline",
    cron_string: convertCronExperssion(task.cron_string),
  })),
);

const manualTasksUI = computed(() =>
  manualTasks.value.map((task) => ({ ...task, icon: "mdi-broom" })),
);

const completedStatuses = computed(() =>
  taskStatuses.value.filter(
    (task) => !["queued", "started"].includes(task.status),
  ),
);

function isTaskRunning(name: string) {
  return taskStatuses.value.some(
    (s) => s.task_name === name && ["queued", "started"].includes(s.status),
  );
}

async function runTask(name: string, title: string) {
  try {
    await taskApi.runTask(name);
    snackbar.success(t("settings.task-started", { title }), {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    const e = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      e?.response?.data?.detail ||
        e?.response?.statusText ||
        e?.message ||
        t("settings.task-failed"),
      { icon: "mdi-close-circle" },
    );
  }
}

async function fetchTaskStatus() {
  try {
    await tasksStore.fetchTaskStatus();
  } catch (err) {
    console.error("Error fetching task status:", err);
  }
}

let refreshInterval: number | null = null;

onMounted(() => {
  void fetchTaskStatus();
  refreshInterval = window.setInterval(() => {
    void fetchTaskStatus();
  }, 5000);
});

onUnmounted(() => {
  if (refreshInterval) clearInterval(refreshInterval);
});

function statusInfo(task: TaskStatusResponse) {
  return TaskStatusItem[task.status] ?? TaskStatusItem.queued;
}
</script>

<template>
  <SettingsSection :title="t('settings.tasks')" icon="mdi-pulse">
    <!-- Watcher -->
    <template v-if="watcherTasksUI.length > 0">
      <div class="r-v2-tasks__sub-heading">{{ t("settings.watcher") }}</div>
      <div class="r-v2-tasks__row">
        <div
          v-for="task in watcherTasksUI"
          :key="task.name"
          class="r-v2-tasks__cell"
        >
          <RIcon
            :icon="task.icon"
            size="18"
            class="r-v2-tasks__icon"
            :class="{ 'r-v2-tasks__icon--off': !task.enabled }"
          />
          <div class="r-v2-tasks__info">
            <span
              class="r-v2-tasks__name"
              :class="{ 'r-v2-tasks__name--off': !task.enabled }"
            >
              {{ task.title }}
            </span>
            <span class="r-v2-tasks__desc">{{ task.description }}</span>
          </div>
        </div>
      </div>
    </template>

    <!-- Scheduled -->
    <template v-if="scheduledTasksUI.length > 0">
      <div class="r-v2-tasks__sub-heading">{{ t("settings.scheduled") }}</div>
      <div class="r-v2-tasks__row r-v2-tasks__row--two-col">
        <div
          v-for="task in scheduledTasksUI"
          :key="task.name"
          class="r-v2-tasks__cell"
        >
          <RIcon
            :icon="task.icon"
            size="18"
            class="r-v2-tasks__icon"
            :class="{ 'r-v2-tasks__icon--off': !task.enabled }"
          />
          <div class="r-v2-tasks__info">
            <span
              class="r-v2-tasks__name"
              :class="{ 'r-v2-tasks__name--off': !task.enabled }"
            >
              {{ task.title }}
            </span>
            <span class="r-v2-tasks__desc">
              {{ task.description }}
              <span v-if="task.cron_string" class="r-v2-tasks__schedule">
                · {{ task.cron_string }}
              </span>
            </span>
          </div>
          <button
            v-if="task.manual_run && task.enabled"
            type="button"
            class="r-v2-tasks__run-btn"
            :disabled="isTaskRunning(task.name)"
            :aria-label="t('settings.run-task', { title: task.title })"
            :title="t('settings.run-task', { title: task.title })"
            @click="runTask(task.name, task.title)"
          >
            <RIcon icon="mdi-play" size="14" />
          </button>
        </div>
      </div>
    </template>

    <!-- Manual -->
    <template v-if="manualTasksUI.length > 0">
      <div class="r-v2-tasks__sub-heading">{{ t("settings.manual") }}</div>
      <div class="r-v2-tasks__row r-v2-tasks__row--two-col">
        <div
          v-for="task in manualTasksUI"
          :key="task.name"
          class="r-v2-tasks__cell"
        >
          <RIcon :icon="task.icon" size="18" class="r-v2-tasks__icon" />
          <div class="r-v2-tasks__info">
            <span class="r-v2-tasks__name">{{ task.title }}</span>
            <span class="r-v2-tasks__desc">{{ task.description }}</span>
          </div>
          <button
            type="button"
            class="r-v2-tasks__run-btn"
            :disabled="isTaskRunning(task.name)"
            :aria-label="t('settings.run-task', { title: task.title })"
            :title="t('settings.run-task', { title: task.title })"
            @click="runTask(task.name, task.title)"
          >
            <RIcon icon="mdi-play" size="14" />
          </button>
        </div>
      </div>
    </template>

    <!-- Task history -->
    <div class="r-v2-tasks__sub-heading">{{ t("settings.task-history") }}</div>
    <div
      v-if="completedStatuses.length === 0"
      class="r-v2-tasks__history-empty"
    >
      <RIcon icon="mdi-information-outline" size="14" />
      {{ t("settings.no-tasks-in-history") }}
    </div>
    <div v-else class="r-v2-tasks__history">
      <div
        v-for="entry in completedStatuses"
        :key="`${entry.task_id}-${entry.status}`"
        class="r-v2-tasks__history-row"
      >
        <span
          class="r-v2-tasks__history-status"
          :class="`r-v2-tasks__history-status--${statusInfo(entry).status}`"
        >
          {{ statusInfo(entry).text }}
        </span>
        <span class="r-v2-tasks__history-name">{{ entry.task_name }}</span>
        <span class="r-v2-tasks__history-when">
          {{ entry.ended_at ? formatTimestamp(entry.ended_at, locale) : "" }}
        </span>
      </div>
    </div>

    <RBtn
      v-if="taskStatuses.length === 0 && !manualTasksUI.length"
      variant="text"
      class="r-v2-tasks__loading"
      disabled
    >
      <RSpinner :size="14" />
      {{ t("common.loading-ellipsis") }}
    </RBtn>
  </SettingsSection>
</template>

<style scoped>
.r-v2-tasks__sub-heading {
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: var(--r-color-fg-faint);
  padding: 10px 16px 4px;
}
.r-v2-tasks__sub-heading + .r-v2-tasks__sub-heading {
  border-top: 1px solid var(--r-color-border);
}

.r-v2-tasks__row {
  display: flex;
  flex-direction: column;
}
.r-v2-tasks__row--two-col {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}
html[data-bp~="xs"] .r-v2-tasks__row--two-col {
  grid-template-columns: 1fr;
}

.r-v2-tasks__cell {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-top: 1px solid var(--r-color-border);
}

.r-v2-tasks__icon {
  flex-shrink: 0;
  color: var(--r-color-brand-primary);
}
.r-v2-tasks__icon--off {
  color: var(--r-color-fg-faint);
}

.r-v2-tasks__info {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.r-v2-tasks__name {
  font-size: 13px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}
.r-v2-tasks__name--off {
  color: var(--r-color-fg-muted);
}

.r-v2-tasks__desc {
  font-size: 11px;
  color: var(--r-color-fg-muted);
  line-height: 1.4;
}
.r-v2-tasks__schedule {
  font-family: var(--r-font-family-mono, monospace);
  color: var(--r-color-fg-faint);
}

.r-v2-tasks__run-btn {
  flex-shrink: 0;
  width: 32px;
  height: 32px;
  border-radius: 50%;
  border: 1px solid var(--r-color-border);
  background: var(--r-color-surface);
  color: var(--r-color-brand-primary);
  cursor: pointer;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  transition:
    background var(--r-motion-fast) var(--r-motion-ease-out),
    border-color var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-tasks__run-btn:hover:not(:disabled) {
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  border-color: color-mix(
    in srgb,
    var(--r-color-brand-primary) 50%,
    transparent
  );
}
.r-v2-tasks__run-btn:disabled {
  opacity: 0.4;
  cursor: not-allowed;
}

.r-v2-tasks__history {
  display: flex;
  flex-direction: column;
}
.r-v2-tasks__history-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 16px;
  border-top: 1px solid var(--r-color-border);
  font-size: 12px;
}
.r-v2-tasks__history-status {
  flex-shrink: 0;
  display: inline-block;
  font-size: 10px;
  font-weight: var(--r-font-weight-bold);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  padding: 2px 8px;
  border-radius: 4px;
  background: var(--r-color-surface);
  color: var(--r-color-fg-muted);
}
.r-v2-tasks__history-status--success {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 14%,
    transparent
  );
  color: var(--r-color-success);
}
.r-v2-tasks__history-status--error {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 14%,
    transparent
  );
  color: var(--r-color-danger);
}
.r-v2-tasks__history-status--primary {
  background: color-mix(in srgb, var(--r-color-brand-primary) 14%, transparent);
  color: var(--r-color-brand-primary);
}
.r-v2-tasks__history-name {
  flex: 1;
  font-weight: var(--r-font-weight-medium);
  color: var(--r-color-fg-secondary);
}
.r-v2-tasks__history-when {
  color: var(--r-color-fg-faint);
  white-space: nowrap;
}
.r-v2-tasks__history-empty {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 12px 16px;
  border-top: 1px solid var(--r-color-border);
  font-size: 12px;
  color: var(--r-color-fg-muted);
}

.r-v2-tasks__loading {
  align-self: flex-start;
}
</style>
