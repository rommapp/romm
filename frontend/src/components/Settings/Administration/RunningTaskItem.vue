<script setup lang="ts">
import { computed } from "vue";
import type {
  ScanTaskStatusResponse,
  ConversionTaskStatusResponse,
  CleanupTaskStatusResponse,
  UpdateTaskStatusResponse,
} from "@/__generated__";
import TaskProgressDisplay from "./tasks/TaskProgressDisplay.vue";

const props = defineProps<{
  task:
    | ScanTaskStatusResponse
    | ConversionTaskStatusResponse
    | CleanupTaskStatusResponse
    | UpdateTaskStatusResponse;
}>();

const statusIconColor = computed(() => {
  switch (props.task.status) {
    case "queued":
      return {
        color: "orange",
        icon: "mdi-clock-outline",
      };
    case "started":
      return {
        color: "blue",
        icon: "mdi-loading",
      };
    case "finished":
      return {
        color: "green",
        icon: "mdi-check-circle",
      };
    case "failed":
      return {
        color: "red",
        icon: "mdi-alert-circle",
      };
    case "stopped":
      return {
        color: "grey",
        icon: "mdi-stop-circle",
      };
    case "canceled":
      return {
        color: "grey",
        icon: "mdi-stop-circle",
      };
    default:
      return {
        color: "grey",
        icon: "mdi-help-circle-outline",
      };
  }
});

const getTaskDuration = () => {
  if (!props.task.started_at) return "Not started";

  const startTime = new Date(props.task.started_at);
  const endTime = props.task.ended_at
    ? new Date(props.task.ended_at)
    : new Date();
  const duration = endTime.getTime() - startTime.getTime();

  if (duration < 1000) return "< 1s";
  if (duration < 60000) return `${Math.round(duration / 1000)}s`;
  if (duration < 3600000) return `${Math.round(duration / 60000)}m`;
  return `${Math.round(duration / 3600000)}h`;
};
</script>

<template>
  <v-card
    elevation="2"
    class="task-card"
    :class="{
      'task-card--running': task.status === 'started',
      'task-card--queued': task.status === 'queued',
      'task-card--finished': task.status === 'finished',
      'task-card--failed': task.status === 'failed',
      'task-card--stopped': task.status === 'stopped',
      'task-card--canceled': task.status === 'canceled',
    }"
  >
    <!-- Header Section -->
    <div class="task-header">
      <div class="task-header__left">
        <div class="task-icon-wrapper">
          <v-icon
            :color="statusIconColor.color"
            :icon="statusIconColor.icon"
            size="24"
            :class="{ 'task-icon--spinning': task.status === 'started' }"
          />
        </div>
        <div class="task-info">
          <h3 class="task-title">{{ task.task_name }}</h3>
          <div class="task-meta">
            <span class="task-type">{{ task.task_type }}</span>
            <span class="task-separator">•</span>
            <span class="task-duration">{{ getTaskDuration() }}</span>
          </div>
        </div>
      </div>
      <div class="task-header__right">
        <v-chip
          :color="statusIconColor.color"
          size="small"
          variant="flat"
          class="task-status-chip"
        >
          <v-icon
            :icon="statusIconColor.icon"
            size="16"
            class="mr-1"
            :class="{ 'task-icon--spinning': task.status === 'started' }"
          />
          {{ task.status }}
        </v-chip>
      </div>
    </div>

    <!-- Progress Section -->
    <TaskProgressDisplay :task="task" />
  </v-card>
</template>

<style scoped>
.task-card {
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.05) 0%,
    rgba(255, 255, 255, 0.02) 100%
  );
  transition: all 0.3s ease;
  overflow: hidden;
}

.task-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 8px 25px rgba(0, 0, 0, 0.15);
  border-color: rgba(255, 255, 255, 0.2);
}

.task-card--running {
  border-left: 4px solid #2196f3;
  background: linear-gradient(
    135deg,
    rgba(33, 150, 243, 0.1) 0%,
    rgba(33, 150, 243, 0.05) 100%
  );
}

.task-card--queued {
  border-left: 4px solid #ff9800;
  background: linear-gradient(
    135deg,
    rgba(255, 152, 0, 0.1) 0%,
    rgba(255, 152, 0, 0.05) 100%
  );
}

.task-card--finished {
  border-left: 4px solid #4caf50;
  background: linear-gradient(
    135deg,
    rgba(76, 175, 80, 0.1) 0%,
    rgba(76, 175, 80, 0.05) 100%
  );
}

.task-card--failed {
  border-left: 4px solid #f44336;
  background: linear-gradient(
    135deg,
    rgba(244, 67, 54, 0.1) 0%,
    rgba(244, 67, 54, 0.05) 100%
  );
}

.task-card--stopped,
.task-card--canceled {
  border-left: 4px solid #9e9e9e;
  background: linear-gradient(
    135deg,
    rgba(158, 158, 158, 0.1) 0%,
    rgba(158, 158, 158, 0.05) 100%
  );
}

.task-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.task-header__left {
  display: flex;
  align-items: center;
  gap: 16px;
  flex: 1;
}

.task-icon-wrapper {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.1);
  backdrop-filter: blur(10px);
}

.task-icon--spinning {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

.task-info {
  flex: 1;
}

.task-title {
  font-size: 18px;
  font-weight: 600;
  color: #ffffff;
  margin: 0 0 4px 0;
  line-height: 1.3;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  color: rgba(255, 255, 255, 0.7);
}

.task-type {
  font-weight: 500;
  color: rgba(255, 255, 255, 0.9);
}

.task-separator {
  color: rgba(255, 255, 255, 0.4);
}

.task-duration {
  font-family: "Monaco", "Menlo", monospace;
  background: rgba(255, 255, 255, 0.1);
  padding: 2px 8px;
  border-radius: 6px;
  font-size: 12px;
}

.task-header__right {
  display: flex;
  align-items: center;
}

.task-status-chip {
  font-weight: 600;
  text-transform: capitalize;
  border-radius: 20px;
  padding: 8px 16px;
}

/* Responsive Design */
@media (max-width: 768px) {
  .task-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 16px;
  }

  .task-header__right {
    align-self: flex-end;
  }

  .task-details__grid {
    grid-template-columns: 1fr;
  }

  .task-meta {
    flex-direction: column;
    align-items: flex-start;
    gap: 4px;
  }

  .task-separator {
    display: none;
  }
}
</style>
