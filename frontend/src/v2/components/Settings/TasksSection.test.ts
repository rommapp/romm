import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { CleanupTaskStatusResponse } from "@/__generated__/models/CleanupTaskStatusResponse";
import type { TaskInfo } from "@/__generated__/models/TaskInfo";
import TasksSection from "./TasksSection.vue";

const { getTasks, getTaskStatus, runTask } = vi.hoisted(() => ({
  getTasks: vi.fn(),
  getTaskStatus: vi.fn(),
  runTask: vi.fn(),
}));

vi.mock("@/services/api/task", () => ({
  default: { getTasks, getTaskStatus, runTask },
}));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: "en_US" } }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

const CLEANUP_TASK: TaskInfo = {
  name: "cleanup_zip_cache",
  type: "cleanup",
  title: "Scheduled ZIP cache cleanup",
  description: "Removes stale cached ZIP files",
  enabled: true,
  manual_run: true,
  cron_string: "",
};

function status(
  overrides: Partial<CleanupTaskStatusResponse> = {},
): CleanupTaskStatusResponse {
  return {
    task_key: null,
    task_name: "Scheduled ZIP cache cleanup",
    task_id: "job-1",
    task_type: "cleanup",
    status: "started",
    created_at: null,
    enqueued_at: null,
    started_at: null,
    ended_at: null,
    meta: { cleanup_stats: null },
    ...overrides,
  };
}

async function mountSection() {
  const wrapper = mount(TasksSection, {
    global: {
      stubs: {
        SettingsSection: { template: "<div><slot /></div>" },
        RBtn: true,
        RIcon: true,
        RSpinner: true,
      },
    },
  });
  await flushPromises();
  return wrapper;
}

function runButton(wrapper: Awaited<ReturnType<typeof mountSection>>) {
  return wrapper.get("button.r-v2-tasks__run-btn");
}

describe("TasksSection", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    getTasks.mockReset();
    getTasks.mockResolvedValue({
      data: { watcher: [], scheduled: [], manual: [CLEANUP_TASK] },
    });
    getTaskStatus.mockReset();
    getTaskStatus.mockResolvedValue({ data: [] });
    runTask.mockReset();
    runTask.mockResolvedValue({ data: { task_id: "job-1" } });
  });

  it("disables the run button while that task's job is in flight", async () => {
    getTaskStatus.mockResolvedValue({
      data: [status({ task_key: "cleanup_zip_cache" })],
    });

    const wrapper = await mountSection();

    expect(runButton(wrapper).attributes("disabled")).toBeDefined();
    wrapper.unmount();
  });

  it("leaves the button live when only the display title matches", async () => {
    getTaskStatus.mockResolvedValue({
      data: [
        status({ task_key: "some_other_task", task_name: "cleanup_zip_cache" }),
      ],
    });

    const wrapper = await mountSection();

    expect(runButton(wrapper).attributes("disabled")).toBeUndefined();
    wrapper.unmount();
  });

  it("holds the button from the click, before any poll has seen the job", async () => {
    let finishRun = () => {};
    runTask.mockReturnValue(
      new Promise((resolve) => {
        finishRun = () => resolve({ data: { task_id: "job-1" } });
      }),
    );

    const wrapper = await mountSection();
    await runButton(wrapper).trigger("click");

    expect(runButton(wrapper).attributes("disabled")).toBeDefined();
    expect(runTask).toHaveBeenCalledTimes(1);

    finishRun();
    await flushPromises();
    wrapper.unmount();
  });

  it("asks for the status again rather than waiting out the poll", async () => {
    const wrapper = await mountSection();
    getTaskStatus.mockClear();

    await runButton(wrapper).trigger("click");
    await flushPromises();

    expect(getTaskStatus).toHaveBeenCalledTimes(1);
    wrapper.unmount();
  });

  it("leaves the button live for a job that carries no key", async () => {
    // A scan a client started itself answers to no registry entry.
    getTaskStatus.mockResolvedValue({
      data: [status({ task_name: "Quick Scan" })],
    });

    const wrapper = await mountSection();

    expect(runButton(wrapper).attributes("disabled")).toBeUndefined();
    wrapper.unmount();
  });
});
