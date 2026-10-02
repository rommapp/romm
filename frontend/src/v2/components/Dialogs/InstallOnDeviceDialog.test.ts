import { flushPromises, mount, type VueWrapper } from "@vue/test-utils";
import mitt, { type Emitter } from "mitt";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { DeviceSchema, InstallRequestSchema } from "@/__generated__";
import type { SimpleRom } from "@/stores/roms";
import type { Events } from "@/types/emitter";
import InstallOnDeviceDialog from "./InstallOnDeviceDialog.vue";

const {
  fetchDevices,
  fetchOnlineDeviceIds,
  fetchRomInstalls,
  createInstall,
  cancelInstall,
  socketHandlers,
} = vi.hoisted(() => ({
  fetchDevices: vi.fn(),
  fetchOnlineDeviceIds: vi.fn(),
  fetchRomInstalls: vi.fn(),
  createInstall: vi.fn(),
  cancelInstall: vi.fn(),
  socketHandlers: new Map<string, (payload: unknown) => void>(),
}));

vi.mock("vue-i18n");

vi.mock("@/services/api/device", () => ({
  default: { fetchDevices, fetchOnlineDeviceIds },
}));

vi.mock("@/services/api/device-install", () => ({
  default: { fetchRomInstalls, createInstall, cancelInstall },
}));

vi.mock("@/v2/composables/useSocketEvent", () => ({
  useSocketEvent: (event: string, handler: (payload: unknown) => void) => {
    socketHandlers.set(event, handler);
  },
}));

vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ mdAndUp: ref(true) }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ error: vi.fn() }),
}));

const ROM = { id: 7, name: "Zelda", fs_name: "zelda.zip" } as SimpleRom;

function device(id: string, install = true): DeviceSchema {
  return {
    id,
    name: id,
    capabilities: install ? { remote_install: true } : null,
    last_seen: null,
  } as DeviceSchema;
}

function installRequest(
  overrides: Partial<InstallRequestSchema> = {},
): InstallRequestSchema {
  return {
    id: "req-1",
    user_id: 1,
    device_id: "handheld",
    rom_id: ROM.id,
    file_ids: [10],
    status: "pending",
    reason: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function mountDialog(emitter: Emitter<Events>): VueWrapper {
  return mount(InstallOnDeviceDialog, {
    global: {
      provide: { emitter },
      stubs: {
        RDialog: {
          props: { modelValue: { type: Boolean, default: false } },
          emits: ["update:modelValue", "close"],
          template: `<div v-if="modelValue">
            <slot name="content" />
            <button data-test-close @click="$emit('update:modelValue', false); $emit('close')" />
          </div>`,
        },
        RCheckbox: {
          props: {
            modelValue: { type: Boolean, default: false },
            disabled: { type: Boolean, default: false },
            subtitle: { type: String, default: undefined },
          },
          emits: ["update:modelValue"],
          template: `<label data-test-device>
            <input type="checkbox" :checked="modelValue" :disabled="disabled"
              @change="$emit('update:modelValue', $event.target.checked)" />
            <slot />
            <span data-test-subtitle>{{ subtitle }}</span>
          </label>`,
        },
        RBtn: true,
        RIcon: true,
        RSpinner: true,
        REmptyState: true,
      },
    },
  });
}

async function open(devices: DeviceSchema[] = [device("handheld")]) {
  fetchDevices.mockResolvedValue({ data: devices });
  const emitter = mitt<Events>();
  const wrapper = mountDialog(emitter);
  emitter.emit("showInstallOnDeviceDialog", ROM);
  await flushPromises();
  return wrapper;
}

async function toggle(wrapper: VueWrapper, checked: boolean) {
  await wrapper.find("[data-test-device] input").setValue(checked);
}

describe("InstallOnDeviceDialog", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    socketHandlers.clear();
    fetchOnlineDeviceIds.mockResolvedValue({ data: [] });
    fetchRomInstalls.mockResolvedValue({ data: [] });
    createInstall.mockImplementation((deviceId: string) =>
      Promise.resolve({ data: installRequest({ device_id: deviceId }) }),
    );
    cancelInstall.mockResolvedValue({
      data: installRequest({ status: "cancelled" }),
    });
  });

  it("keeps a reopened dialog's send busy when an earlier one finishes", async () => {
    fetchDevices.mockResolvedValue({ data: [device("handheld")] });
    const releases: Array<() => void> = [];
    createInstall.mockImplementation(
      (deviceId: string) =>
        new Promise((resolve) => {
          releases.push(() =>
            resolve({ data: installRequest({ device_id: deviceId }) }),
          );
        }),
    );
    const emitter = mitt<Events>();
    const wrapper = mountDialog(emitter);

    emitter.emit("showInstallOnDeviceDialog", ROM);
    await flushPromises();
    await toggle(wrapper, true);
    await wrapper.find("[data-test-close]").trigger("click");
    emitter.emit("showInstallOnDeviceDialog", { ...ROM, id: 8 });
    await flushPromises();
    await toggle(wrapper, true);
    vi.advanceTimersByTime(3000);
    await flushPromises();
    expect(createInstall).toHaveBeenCalledTimes(2);

    releases[0]?.();
    await flushPromises();

    expect(
      wrapper.find("[data-test-device] input").attributes("disabled"),
    ).toBeDefined();
  });

  it("lists only the devices that accept installs", async () => {
    const wrapper = await open([device("handheld"), device("tv", false)]);

    expect(wrapper.findAll("[data-test-device]")).toHaveLength(1);
    expect(wrapper.text()).toContain("handheld");
  });

  it("sends after the preparing delay", async () => {
    const wrapper = await open();

    await toggle(wrapper, true);
    expect(wrapper.find("[data-test-subtitle]").text()).toBe(
      "rom.install-on-device-preparing",
    );
    vi.advanceTimersByTime(2999);
    expect(createInstall).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    await flushPromises();

    expect(createInstall).toHaveBeenCalledOnce();
    expect(createInstall).toHaveBeenCalledWith("handheld", { rom_id: ROM.id });
    expect(wrapper.find("[data-test-subtitle]").text()).toBe(
      "rom.install-on-device-status-pending",
    );
  });

  it("sends nothing when unchecked while preparing", async () => {
    const wrapper = await open();

    await toggle(wrapper, true);
    vi.advanceTimersByTime(2000);
    await toggle(wrapper, false);
    vi.advanceTimersByTime(10_000);
    await flushPromises();

    expect(createInstall).not.toHaveBeenCalled();
  });

  it("sends a preparing install at once when closed", async () => {
    const wrapper = await open();

    await toggle(wrapper, true);
    await wrapper.find("[data-test-close]").trigger("click");
    await flushPromises();

    expect(createInstall).toHaveBeenCalledOnce();
    vi.advanceTimersByTime(10_000);
    expect(createInstall).toHaveBeenCalledOnce();
  });

  it("cancels a live request when unchecked", async () => {
    fetchRomInstalls.mockResolvedValue({ data: [installRequest()] });
    const wrapper = await open();

    await toggle(wrapper, false);
    await flushPromises();

    expect(cancelInstall).toHaveBeenCalledWith("handheld", "req-1");
    expect(wrapper.find("[data-test-subtitle]").text()).toBe(
      "rom.install-on-device-status-cancelled",
    );
  });

  it("follows socket updates for the open rom only", async () => {
    const wrapper = await open();
    const update = socketHandlers.get("install:updated");
    if (!update) throw new Error("the dialog never subscribed");

    update(installRequest({ rom_id: 99, status: "taken" }));
    await flushPromises();
    expect(wrapper.find("[data-test-subtitle]").text()).toBe("");

    update(installRequest({ status: "taken" }));
    await flushPromises();
    expect(wrapper.find("[data-test-subtitle]").text()).toBe(
      "rom.install-on-device-status-taken",
    );
  });

  it("keeps the newer request when an older one arrives late", async () => {
    const wrapper = await open();
    const update = socketHandlers.get("install:updated");
    if (!update) throw new Error("the dialog never subscribed");

    update(
      installRequest({
        id: "req-2",
        status: "taken",
        created_at: "2026-01-02T00:00:00Z",
      }),
    );
    update(installRequest({ status: "cancelled" }));
    await flushPromises();

    expect(wrapper.find("[data-test-subtitle]").text()).toBe(
      "rom.install-on-device-status-taken",
    );
  });

  it("keeps the newer status when a stale one of the same request arrives late", async () => {
    const wrapper = await open();
    const update = socketHandlers.get("install:updated");
    if (!update) throw new Error("the dialog never subscribed");

    update(
      installRequest({ status: "taken", updated_at: "2026-01-01T00:00:05Z" }),
    );
    update(installRequest({ status: "pending" }));
    await flushPromises();

    expect(wrapper.find("[data-test-subtitle]").text()).toBe(
      "rom.install-on-device-status-taken",
    );
  });

  it("keeps a socket update that lands while the dialog loads", async () => {
    let resolveInstalls: (value: {
      data: InstallRequestSchema[];
    }) => void = () => {};
    fetchRomInstalls.mockReturnValue(
      new Promise((resolve) => {
        resolveInstalls = resolve;
      }),
    );
    fetchDevices.mockResolvedValue({ data: [device("handheld")] });
    const emitter = mitt<Events>();
    const wrapper = mountDialog(emitter);
    emitter.emit("showInstallOnDeviceDialog", ROM);
    const update = socketHandlers.get("install:updated");
    if (!update) throw new Error("the dialog never subscribed");

    update(
      installRequest({ status: "done", updated_at: "2026-01-01T00:00:09Z" }),
    );
    resolveInstalls({
      data: [
        installRequest({ status: "taken", updated_at: "2026-01-01T00:00:05Z" }),
      ],
    });
    await flushPromises();

    expect(wrapper.find("[data-test-subtitle]").text()).toBe(
      "rom.install-on-device-status-done",
    );
  });

  it("locks a delivered install", async () => {
    fetchRomInstalls.mockResolvedValue({ data: [] });
    const wrapper = await open();
    const update = socketHandlers.get("install:updated");
    if (!update) throw new Error("the dialog never subscribed");

    update(installRequest({ status: "done" }));
    await flushPromises();

    const input = wrapper.find("[data-test-device] input");
    expect(input.attributes("disabled")).toBeDefined();
    expect((input.element as HTMLInputElement).checked).toBe(true);
  });
});
