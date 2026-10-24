import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DeviceSchema } from "@/__generated__";
import deviceApi from "@/services/api/device";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";
import Devices from "./Devices.vue";

const mocks = vi.hoisted(() => ({
  confirm: vi.fn(),
  snackbarError: vi.fn(),
  snackbarSuccess: vi.fn(),
  socketHandlers: new Map<string, (payload: unknown) => void>(),
}));

vi.mock("vue-i18n");
vi.mock("@/services/api/device", () => ({
  default: {
    fetchDevices: vi.fn(),
    updateDevice: vi.fn(),
    deleteDevice: vi.fn(),
    addConsole: vi.fn(),
    updateConsole: vi.fn(),
    syncConsole: vi.fn(),
  },
}));
vi.mock("@/composables/useSocketEvent", () => ({
  useSocketEvent: (event: string, handler: (payload: unknown) => void) => {
    mocks.socketHandlers.set(event, handler);
    return { off: vi.fn() };
  },
}));
vi.mock("@/composables/useConfirm", () => ({
  useConfirm: () => mocks.confirm,
}));
vi.mock("@/composables/useSnackbar", () => ({
  useSnackbar: () => ({
    success: mocks.snackbarSuccess,
    error: mocks.snackbarError,
  }),
}));

function device(overrides: Partial<DeviceSchema> = {}): DeviceSchema {
  return {
    id: "dev-a",
    user_id: 1,
    name: "Firefox on macOS",
    platform: "Web",
    client: "web",
    client_version: null,
    ip_address: null,
    mac_address: null,
    hostname: null,
    client_device_identifier: null,
    sync_mode: "api",
    sync_enabled: true,
    sync_config: null,
    capabilities: null,
    last_seen: "2026-10-01T00:00:00Z",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

const RTable = {
  props: {
    items: { type: Array, default: () => [] },
    emptyMessage: { type: String, default: "" },
  },
  template: `
    <div>
      <div v-for="row in items" :key="row.id" class="row" :data-id="row.id">
        <slot name="cell.name" :row="row" />
        <slot name="cell.last_seen" :row="row" />
        <slot name="cell.sync" :row="row" />
        <slot name="cell.actions" :row="row" />
      </div>
      <p v-if="!items.length" class="empty">{{ emptyMessage }}</p>
    </div>`,
};

const RSwitch = {
  props: {
    modelValue: { type: Boolean, default: false },
    disabled: { type: Boolean, default: false },
  },
  emits: ["update:modelValue"],
  template: `<button type="button" class="switch" :data-on="modelValue" :disabled="disabled" @click="$emit('update:modelValue', !modelValue)" />`,
};

const RBtn = {
  props: { icon: { type: String, default: "" } },
  emits: ["click"],
  template: `<button type="button" :data-icon="icon" @click="$emit('click')"><slot /></button>`,
};

const RenameDeviceDialog = {
  name: "RenameDeviceDialog",
  props: {
    modelValue: { type: Boolean, default: false },
    name: { type: String, default: "" },
  },
  emits: ["update:modelValue", "submit"],
  template: `<div class="rename" :data-open="modelValue" :data-name="name" />`,
};

const ConsoleDialog = {
  name: "ConsoleDialog",
  props: {
    modelValue: { type: Boolean, default: false },
    device: { type: Object, default: null },
  },
  emits: ["update:modelValue", "submit"],
  template: `<div class="ps3-dialog" :data-open="modelValue" />`,
};

const ps3 = (overrides: Partial<DeviceSchema> = {}) =>
  device({
    id: "ps3",
    name: "PS3",
    platform: "PS3",
    client: "ps3",
    ip_address: "192.168.1.115",
    sync_mode: "push_pull",
    sync_config: { poll_interval_minutes: 15 },
    ...overrides,
  });

function signIn(scopes: string[]) {
  storeAuth().setCurrentUser(userFixture({ id: 1, oauth_scopes: scopes }));
}

function mountDevices() {
  return mount(Devices, {
    global: {
      stubs: {
        RTable,
        RSwitch,
        RBtn,
        RChip: { template: "<span class='chip'><slot /></span>" },
        RenameDeviceDialog,
        ConsoleDialog,
      },
    },
  });
}

function row(wrapper: ReturnType<typeof mountDevices>, id: string) {
  return wrapper.get(`.row[data-id='${id}']`);
}

beforeEach(() => {
  vi.clearAllMocks();
  mocks.socketHandlers.clear();
  localStorage.clear();
  signIn(["devices.read", "devices.write"]);
  vi.mocked(deviceApi.fetchDevices).mockResolvedValue({
    data: [
      device({
        id: "dev-old",
        name: "Steam Deck",
        platform: "Linux",
        client: "argosy",
        last_seen: "2026-01-01T00:00:00Z",
      }),
      device(),
    ],
  } as never);
});

describe("Devices", () => {
  it("lists the most recently active first and marks this browser", async () => {
    localStorage.setItem("romm:browser-device:1", "dev-a");
    const wrapper = mountDevices();
    await flushPromises();

    const ids = wrapper.findAll(".row").map((r) => r.attributes("data-id"));
    expect(ids).toEqual(["dev-a", "dev-old"]);
    expect(row(wrapper, "dev-a").find(".chip").text()).toBe(
      "settings.device-this-browser",
    );
    expect(row(wrapper, "dev-old").find(".chip").exists()).toBe(false);
    expect(row(wrapper, "dev-old").text()).toContain("Linux · argosy");
  });

  it("shows the empty state when there are no devices", async () => {
    vi.mocked(deviceApi.fetchDevices).mockResolvedValue({ data: [] } as never);
    const wrapper = mountDevices();
    await flushPromises();

    expect(wrapper.get(".empty").text()).toBe("settings.devices-empty");
  });

  it("turns sync off at once and keeps it off once saved", async () => {
    vi.mocked(deviceApi.updateDevice).mockResolvedValue({
      data: device({ sync_enabled: false }),
    } as never);
    const wrapper = mountDevices();
    await flushPromises();

    await row(wrapper, "dev-a").get(".switch").trigger("click");
    expect(row(wrapper, "dev-a").get(".switch").attributes("data-on")).toBe(
      "false",
    );
    await flushPromises();

    expect(deviceApi.updateDevice).toHaveBeenCalledWith("dev-a", {
      sync_enabled: false,
    });
    expect(row(wrapper, "dev-a").get(".switch").attributes("data-on")).toBe(
      "false",
    );
  });

  it("restores the switch when the change fails", async () => {
    vi.mocked(deviceApi.updateDevice).mockRejectedValue(new Error("offline"));
    const wrapper = mountDevices();
    await flushPromises();

    await row(wrapper, "dev-a").get(".switch").trigger("click");
    await flushPromises();

    expect(row(wrapper, "dev-a").get(".switch").attributes("data-on")).toBe(
      "true",
    );
    expect(mocks.snackbarError).toHaveBeenCalled();
  });

  it("renames a device", async () => {
    vi.mocked(deviceApi.updateDevice).mockResolvedValue({
      data: device({ name: "Living room" }),
    } as never);
    const wrapper = mountDevices();
    await flushPromises();

    await row(wrapper, "dev-a")
      .get("[data-icon='mdi-pencil-outline']")
      .trigger("click");
    const dialog = wrapper.findComponent(RenameDeviceDialog);
    expect(dialog.props()).toMatchObject({
      modelValue: true,
      name: "Firefox on macOS",
    });
    dialog.vm.$emit("submit", "Living room");
    await flushPromises();

    expect(deviceApi.updateDevice).toHaveBeenCalledWith("dev-a", {
      name: "Living room",
    });
    expect(row(wrapper, "dev-a").text()).toContain("Living room");
    expect(dialog.props("modelValue")).toBe(false);
  });

  it("deletes a device only once confirmed", async () => {
    vi.mocked(deviceApi.deleteDevice).mockResolvedValue({} as never);
    const wrapper = mountDevices();
    await flushPromises();
    const deleteButton = () =>
      row(wrapper, "dev-old").get("[data-icon='mdi-trash-can-outline']");

    mocks.confirm.mockResolvedValueOnce(false);
    await deleteButton().trigger("click");
    await flushPromises();
    expect(deviceApi.deleteDevice).not.toHaveBeenCalled();

    mocks.confirm.mockResolvedValueOnce(true);
    await deleteButton().trigger("click");
    await flushPromises();

    expect(mocks.confirm).toHaveBeenLastCalledWith(
      expect.objectContaining({ tone: "danger" }),
    );
    expect(deviceApi.deleteDevice).toHaveBeenCalledWith("dev-old");
    expect(wrapper.find(".row[data-id='dev-old']").exists()).toBe(false);
  });

  it("is read-only without devices.write", async () => {
    signIn(["devices.read"]);
    const wrapper = mountDevices();
    await flushPromises();

    expect(
      row(wrapper, "dev-a").get(".switch").attributes("disabled"),
    ).toBeDefined();
    expect(row(wrapper, "dev-a").find("[data-icon]").exists()).toBe(false);
  });

  describe("consoles", () => {
    beforeEach(() => {
      vi.mocked(deviceApi.fetchDevices).mockResolvedValue({
        data: [ps3()],
      } as never);
    });

    it("shows the address and check interval", async () => {
      const wrapper = mountDevices();
      await flushPromises();

      expect(row(wrapper, "ps3").text()).toContain(
        "PS3 · 192.168.1.115 · settings.console-every-minutes",
      );
      expect(
        row(wrapper, "ps3").find("[data-icon='mdi-pencil-outline']").exists(),
      ).toBe(false);
    });

    it("syncs a console on request", async () => {
      vi.mocked(deviceApi.syncConsole).mockResolvedValue({} as never);
      const wrapper = mountDevices();
      await flushPromises();

      await row(wrapper, "ps3").get("[data-icon='mdi-sync']").trigger("click");
      await flushPromises();

      expect(deviceApi.syncConsole).toHaveBeenCalledWith("ps3");
      expect(mocks.snackbarSuccess).toHaveBeenCalled();
    });

    it("adds a console from the dialog", async () => {
      vi.mocked(deviceApi.fetchDevices).mockResolvedValue({
        data: [],
      } as never);
      vi.mocked(deviceApi.addConsole).mockResolvedValue({
        data: ps3(),
      } as never);
      const wrapper = mountDevices();
      await flushPromises();

      await wrapper.get("button").trigger("click");
      const dialog = wrapper.findComponent(ConsoleDialog);
      expect(dialog.props()).toMatchObject({ modelValue: true, device: null });
      const payload = {
        console: "ps3",
        name: "PS3",
        ip_address: "192.168.1.115",
      };
      dialog.vm.$emit("submit", payload);
      await flushPromises();

      expect(deviceApi.addConsole).toHaveBeenCalledWith(payload);
      expect(wrapper.find(".row[data-id='ps3']").exists()).toBe(true);
      expect(dialog.props("modelValue")).toBe(false);
    });

    it("edits a console's settings", async () => {
      vi.mocked(deviceApi.updateConsole).mockResolvedValue({
        data: ps3({ ip_address: "192.168.1.20" }),
      } as never);
      const wrapper = mountDevices();
      await flushPromises();

      await row(wrapper, "ps3")
        .get("[data-icon='mdi-cog-outline']")
        .trigger("click");
      const dialog = wrapper.findComponent(ConsoleDialog);
      expect(dialog.props("device")).toMatchObject({ id: "ps3" });
      dialog.vm.$emit("submit", { name: "PS3", ip_address: "192.168.1.20" });
      await flushPromises();

      expect(deviceApi.updateConsole).toHaveBeenCalledWith(
        "ps3",
        expect.objectContaining({ ip_address: "192.168.1.20" }),
      );
      expect(row(wrapper, "ps3").text()).toContain("192.168.1.20");
    });

    it("refreshes when a console sync finishes and reports a failure", async () => {
      const wrapper = mountDevices();
      await flushPromises();
      expect(deviceApi.fetchDevices).toHaveBeenCalledTimes(1);

      mocks.socketHandlers.get("sync:completed")?.({ device_id: "ps3" });
      mocks.socketHandlers.get("sync:completed")?.({ device_id: "dev-a" });
      mocks.socketHandlers.get("sync:error")?.({
        device_id: "ps3",
        error: "Could not connect",
      });
      await flushPromises();

      expect(deviceApi.fetchDevices).toHaveBeenCalledTimes(2);
      expect(mocks.snackbarError).toHaveBeenCalledOnce();
      wrapper.unmount();
    });

    it("hides adding a console without devices.write", async () => {
      signIn(["devices.read"]);
      const wrapper = mountDevices();
      await flushPromises();

      expect(wrapper.text()).not.toContain("settings.console-add");
    });
  });
});
