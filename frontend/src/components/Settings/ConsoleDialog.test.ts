import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { ConsoleProbeResponse, DeviceSchema } from "@/__generated__";
import deviceApi from "@/services/api/device";
import ConsoleDialog from "./ConsoleDialog.vue";

vi.mock("vue-i18n");
vi.mock("@/services/api/device", () => ({
  default: { probeConsole: vi.fn() },
}));

const RDialog = {
  template: `<div><slot name="header" /><slot name="content" /><slot name="footer" /></div>`,
};

const RForm = {
  emits: ["update:modelValue", "submit"],
  mounted(this: { $emit: (e: string, v: boolean) => void }) {
    this.$emit("update:modelValue", true);
  },
  template: `<form><slot /></form>`,
};

const RTextField = {
  props: {
    modelValue: { type: [String, Number], default: "" },
    label: { type: String, default: "" },
  },
  emits: ["update:modelValue"],
  template: `<input :data-label="label" :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />`,
};

const RSelect = {
  props: {
    modelValue: { type: String, default: null },
    items: { type: Array, default: () => [] },
    label: { type: String, default: "" },
    disabled: { type: Boolean, default: false },
  },
  emits: ["update:modelValue"],
  template: `
    <select :data-label="label" :value="modelValue" :disabled="disabled" @change="$emit('update:modelValue', $event.target.value)">
      <option v-for="item in items" :key="item.value" :value="item.value">{{ item.title }}</option>
    </select>`,
};

const RBtn = {
  props: { prependIcon: { type: String, default: "" } },
  emits: ["click"],
  template: `<button type="button" :data-icon="prependIcon" @click="$emit('click')"><slot /></button>`,
};

const RAlert = {
  props: {
    type: { type: String, default: "" },
    text: { type: String, default: "" },
  },
  template: `<p class="alert" :data-type="type">{{ text }}</p>`,
};

function mountDialog(device: DeviceSchema | null = null) {
  return mount(ConsoleDialog, {
    props: { modelValue: true, device },
    global: { stubs: { RDialog, RForm, RTextField, RSelect, RBtn, RAlert } },
  });
}

function field(wrapper: ReturnType<typeof mountDialog>, label: string) {
  return wrapper.get(`[data-label='${label}']`);
}

function value(wrapper: ReturnType<typeof mountDialog>, label: string) {
  return (field(wrapper, label).element as HTMLInputElement).value;
}

function answer(data: ConsoleProbeResponse) {
  vi.mocked(deviceApi.probeConsole).mockResolvedValue({ data } as never);
}

async function testConnection(wrapper: ReturnType<typeof mountDialog>) {
  await wrapper.get("[data-icon='mdi-lan-connect']").trigger("click");
  await flushPromises();
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("ConsoleDialog", () => {
  it("lists the profiles a connection test finds, with their names", async () => {
    answer({
      reachable: true,
      is_ftp: true,
      users: [
        { id: "00000001", name: "FIL2K" },
        { id: "00000002", name: null },
      ],
    });
    const wrapper = mountDialog();
    expect(field(wrapper, "settings.console-user").attributes()).toHaveProperty(
      "disabled",
    );
    await field(wrapper, "settings.console-ip-address").setValue(
      "192.168.1.115",
    );

    await testConnection(wrapper);

    expect(deviceApi.probeConsole).toHaveBeenCalledWith({
      console: "ps3",
      ip_address: "192.168.1.115",
      ftp_port: 21,
    });
    expect(
      wrapper.findAll("option").map((o) => [o.attributes("value"), o.text()]),
    ).toEqual(
      expect.arrayContaining([
        ["00000001", "00000001 · FIL2K"],
        ["00000002", "00000002"],
      ]),
    );
    expect(value(wrapper, "settings.console-user")).toBe("00000001");
    expect(wrapper.get(".alert[role='status']").attributes("data-type")).toBe(
      "success",
    );
  });

  it("submits the settings with the chosen profile", async () => {
    answer({
      reachable: true,
      is_ftp: true,
      users: [{ id: "00000001", name: "FIL2K" }],
    });
    const wrapper = mountDialog();
    await field(wrapper, "settings.console-ip-address").setValue(
      " 192.168.1.115 ",
    );
    await field(wrapper, "settings.console-interval").setValue("5");

    await wrapper.get("[data-icon='mdi-check']").trigger("click");
    expect(wrapper.emitted("submit")).toBeUndefined();

    await testConnection(wrapper);
    await wrapper.get("[data-icon='mdi-check']").trigger("click");

    expect(wrapper.emitted("submit")?.[0]?.[0]).toEqual({
      console: "ps3",
      name: "settings.console-ps3",
      ip_address: "192.168.1.115",
      ftp_port: 21,
      user_id: "00000001",
      poll_interval_minutes: 5,
      keep_versions: 10,
    });
  });

  it("tests an edited console at once and keeps its profile", async () => {
    answer({
      reachable: true,
      is_ftp: true,
      users: [
        { id: "00000001", name: "FIL2K" },
        { id: "00000002", name: "GUEST" },
      ],
    });
    const wrapper = mountDialog({
      id: "ps3",
      user_id: 1,
      name: "Living room",
      platform: "PS3",
      client: "ps3",
      client_version: null,
      ip_address: "192.168.1.20",
      mac_address: null,
      hostname: null,
      client_device_identifier: null,
      sync_mode: "push_pull",
      sync_enabled: true,
      sync_config: { ftp_port: 2121, user_id: "00000002" },
      capabilities: null,
      last_seen: null,
      created_at: "2026-10-24T00:00:00Z",
      updated_at: "2026-10-24T00:00:00Z",
    });
    await flushPromises();

    expect(deviceApi.probeConsole).toHaveBeenCalledWith({
      console: "ps3",
      ip_address: "192.168.1.20",
      ftp_port: 2121,
    });
    expect(value(wrapper, "common.name")).toBe("Living room");
    expect(value(wrapper, "settings.console-user")).toBe("00000002");
    expect(field(wrapper, "settings.console-kind").attributes()).toHaveProperty(
      "disabled",
    );
    expect(field(wrapper, "settings.console-user").attributes()).toHaveProperty(
      "disabled",
    );
  });

  it("takes a PS4's defaults when the kind changes", async () => {
    answer({
      reachable: true,
      is_ftp: true,
      users: [{ id: "1cabafc9", name: "Fil2k" }],
    });
    const wrapper = mountDialog();
    await field(wrapper, "settings.console-kind").setValue("ps4");
    await field(wrapper, "settings.console-ip-address").setValue(
      "192.168.1.177",
    );

    expect(value(wrapper, "settings.console-ftp-port")).toBe("2121");
    expect(value(wrapper, "common.name")).toBe("settings.console-ps4");

    await testConnection(wrapper);
    await wrapper.get("[data-icon='mdi-check']").trigger("click");

    expect(deviceApi.probeConsole).toHaveBeenCalledWith({
      console: "ps4",
      ip_address: "192.168.1.177",
      ftp_port: 2121,
    });
    expect(wrapper.emitted("submit")?.[0]?.[0]).toMatchObject({
      console: "ps4",
      ftp_port: 2121,
      user_id: "1cabafc9",
    });
  });

  it("keeps a port and name the user typed when the kind changes", async () => {
    const wrapper = mountDialog();
    await field(wrapper, "settings.console-ftp-port").setValue("2222");
    await field(wrapper, "common.name").setValue("Den");

    await field(wrapper, "settings.console-kind").setValue("ps4");

    expect(value(wrapper, "settings.console-ftp-port")).toBe("2222");
    expect(value(wrapper, "common.name")).toBe("Den");
  });

  it("opens an edited PS4 as a PS4", async () => {
    answer({ reachable: true, is_ftp: true, users: [] });
    const wrapper = mountDialog({
      id: "ps4",
      user_id: 1,
      name: "Bedroom",
      platform: "PS4",
      client: "ps4",
      client_version: null,
      ip_address: "192.168.1.177",
      mac_address: null,
      hostname: null,
      client_device_identifier: null,
      sync_mode: "push_pull",
      sync_enabled: true,
      sync_config: { user_id: "1cabafc9" },
      capabilities: null,
      last_seen: null,
      created_at: "2026-10-24T00:00:00Z",
      updated_at: "2026-10-24T00:00:00Z",
    });
    await flushPromises();

    expect(value(wrapper, "settings.console-kind")).toBe("ps4");
    expect(value(wrapper, "settings.console-user")).toBe("1cabafc9");
    expect(deviceApi.probeConsole).toHaveBeenCalledWith({
      console: "ps4",
      ip_address: "192.168.1.177",
      ftp_port: 2121,
    });
  });

  it("warns when nothing answers", async () => {
    answer({ reachable: false, is_ftp: false, users: [] });
    const wrapper = mountDialog();
    await field(wrapper, "settings.console-ip-address").setValue("192.168.1.9");

    await testConnection(wrapper);

    expect(wrapper.get(".alert[role='status']").text()).toBe(
      "settings.console-test-unreachable",
    );
  });

  it("forgets a result once the address changes", async () => {
    answer({
      reachable: true,
      is_ftp: true,
      users: [{ id: "00000001", name: "FIL2K" }],
    });
    const wrapper = mountDialog();
    await field(wrapper, "settings.console-ip-address").setValue(
      "192.168.1.115",
    );
    await testConnection(wrapper);

    await field(wrapper, "settings.console-ip-address").setValue(
      "192.168.1.116",
    );

    expect(wrapper.find(".alert[role='status']").exists()).toBe(false);
    expect(
      field(wrapper, "settings.console-user").findAll("option"),
    ).toHaveLength(0);
    await wrapper.get("[data-icon='mdi-check']").trigger("click");
    expect(wrapper.emitted("submit")).toBeUndefined();
  });

  it("ignores a test that answers after the address changed", async () => {
    let answerLate: (value: unknown) => void = () => {};
    vi.mocked(deviceApi.probeConsole).mockReturnValue(
      new Promise((resolve) => {
        answerLate = resolve;
      }) as never,
    );
    const wrapper = mountDialog();
    await field(wrapper, "settings.console-ip-address").setValue(
      "192.168.1.115",
    );
    await wrapper.get("[data-icon='mdi-lan-connect']").trigger("click");

    await field(wrapper, "settings.console-ip-address").setValue(
      "192.168.1.116",
    );
    answerLate({
      data: {
        reachable: true,
        is_ftp: true,
        users: [{ id: "00000001", name: "A" }],
      },
    });
    await flushPromises();

    expect(wrapper.find(".alert[role='status']").exists()).toBe(false);
    expect(
      field(wrapper, "settings.console-user").findAll("option"),
    ).toHaveLength(0);
  });
});
