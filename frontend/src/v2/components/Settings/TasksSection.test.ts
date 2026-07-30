/* eslint-disable vue/one-component-per-file */
import { mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent } from "vue";
import type { TaskInfo } from "@/__generated__/models/TaskInfo";
import storeTasks from "@/stores/tasks";
import TasksSection from "./TasksSection.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: "en_US" }),
}));

vi.mock("@v2/lib", () => ({
  RBtn: defineComponent({ template: "<button><slot /></button>" }),
  RIcon: defineComponent({
    props: { icon: { type: String, default: "" } },
    template: '<i class="r-icon" :data-icon="icon" />',
  }),
  RSpinner: defineComponent({ template: "<div />" }),
}));

vi.mock("@/v2/components/Settings/SettingsSection.vue", () => ({
  default: defineComponent({ template: "<section><slot /></section>" }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

vi.mock("@/services/api/task", () => ({
  default: {
    getTasks: vi.fn(),
    getTaskStatus: vi.fn(),
    runTask: vi.fn(),
  },
}));

function makeTask(overrides: Partial<TaskInfo>): TaskInfo {
  return {
    name: "cleanup_orphaned_resources",
    type: "cleanup",
    title: "Cleanup orphaned resources",
    description: "Clean up orphaned resources in the ROMs directory",
    enabled: true,
    manual_run: true,
    cron_string: "",
    ...overrides,
  } as TaskInfo;
}

function mountWithScheduledTasks(tasks: TaskInfo[]) {
  setActivePinia(createPinia());
  const store = storeTasks();
  vi.spyOn(store, "fetchTasks").mockResolvedValue({
    watcherTasks: [],
    scheduledTasks: tasks,
    manualTasks: [],
  });
  vi.spyOn(store, "fetchTaskStatus").mockResolvedValue([]);
  store.scheduledTasks = tasks;

  return mount(TasksSection);
}

describe("TasksSection", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("renders a task whose schedule is off without blanking the panel", () => {
    // A throw inside the cron computed costs the whole component, so a task
    // with no describable schedule must still render alongside the others.
    const wrapper = mountWithScheduledTasks([makeTask({ cron_string: "" })]);

    expect(wrapper.find("section").exists()).toBe(true);
    expect(wrapper.text()).toContain("Cleanup orphaned resources");
  });

  it("shows no schedule and an off clock when the schedule is off", () => {
    const wrapper = mountWithScheduledTasks([makeTask({ cron_string: "" })]);

    expect(wrapper.text()).not.toContain("every day");
    expect(wrapper.find(".r-v2-tasks__schedule").exists()).toBe(false);
    expect(wrapper.find(".r-icon").attributes("data-icon")).toBe(
      "mdi-clock-remove-outline",
    );
  });

  it("keeps the run button for a manually runnable task with no schedule", () => {
    const wrapper = mountWithScheduledTasks([
      makeTask({ cron_string: "", manual_run: true }),
    ]);

    expect(wrapper.find(".r-v2-tasks__run-btn").exists()).toBe(true);
  });

  it("describes the schedule and shows an on clock when it is on", () => {
    const wrapper = mountWithScheduledTasks([
      makeTask({ cron_string: "0 5 * * *" }),
    ]);

    expect(wrapper.find(".r-v2-tasks__schedule").text()).toContain(
      "at 05:00 AM, every day",
    );
    expect(wrapper.find(".r-icon").attributes("data-icon")).toBe(
      "mdi-clock-check-outline",
    );
  });
});
