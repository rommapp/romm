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
}));

vi.mock("vue-i18n");
vi.mock("@/services/api/device", () => ({
  default: {
    fetchDevices: vi.fn(),
    updateDevice: vi.fn(),
    deleteDevice: vi.fn(),
  },
}));
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => mocks.confirm,
}));
vi.mock("@/v2/composables/useSnackbar", () => ({
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
      },
    },
  });
}

function row(wrapper: ReturnType<typeof mountDevices>, id: string) {
  return wrapper.get(`.row[data-id='${id}']`);
}

beforeEach(() => {
  vi.clearAllMocks();
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

  it("forgets this browser's device once it is removed", async () => {
    localStorage.setItem("romm:browser-device:1", "dev-a");
    vi.mocked(deviceApi.deleteDevice).mockResolvedValue({} as never);
    mocks.confirm.mockResolvedValueOnce(true);
    const wrapper = mountDevices();
    await flushPromises();

    await row(wrapper, "dev-a")
      .get("[data-icon='mdi-trash-can-outline']")
      .trigger("click");
    await flushPromises();

    expect(localStorage.getItem("romm:browser-device:1")).toBeNull();
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
});
