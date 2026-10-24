import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import type { DeviceSchema } from "@/__generated__";
import deviceApi from "@/services/api/device";
import PS3ConsoleDialog from "./PS3ConsoleDialog.vue";

vi.mock("vue-i18n");
vi.mock("@/services/api/device", () => ({
  default: { probePS3: vi.fn() },
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
  return mount(PS3ConsoleDialog, {
    props: { modelValue: true, device },
    global: { stubs: { RDialog, RForm, RTextField, RBtn, RAlert } },
  });
}

function field(wrapper: ReturnType<typeof mountDialog>, label: string) {
  return wrapper.get(`input[data-label='${label}']`);
}

beforeEach(() => {
  vi.clearAllMocks();
});

describe("PS3ConsoleDialog", () => {
  it("submits the settings as numbers", async () => {
    const wrapper = mountDialog();
    await field(wrapper, "settings.ps3-ip-address").setValue(" 192.168.1.115 ");
    await field(wrapper, "settings.ps3-interval").setValue("5");

    await wrapper.get("[data-icon='mdi-check']").trigger("click");

    expect(wrapper.emitted("submit")?.[0]?.[0]).toEqual({
      name: "settings.ps3-default-name",
      ip_address: "192.168.1.115",
      ftp_port: 21,
      ps3_user: "00000001",
      poll_interval_minutes: 5,
      keep_versions: 10,
    });
  });

  it("starts from the console's own settings when editing", () => {
    const wrapper = mountDialog({
      name: "Living room",
      ip_address: "192.168.1.20",
      sync_config: { ftp_port: 2121, keep_versions: 3 },
    } as DeviceSchema);

    expect(
      (field(wrapper, "settings.ps3-ftp-port").element as HTMLInputElement)
        .value,
    ).toBe("2121");
    expect(
      (field(wrapper, "common.name").element as HTMLInputElement).value,
    ).toBe("Living room");
  });

  it("picks a profile the connection test found", async () => {
    vi.mocked(deviceApi.probePS3).mockResolvedValue({
      data: { reachable: true, is_ftp: true, users: ["00000002"] },
    } as never);
    const wrapper = mountDialog();
    await field(wrapper, "settings.ps3-ip-address").setValue("192.168.1.115");

    await wrapper.get("[data-icon='mdi-lan-connect']").trigger("click");
    await flushPromises();

    expect(deviceApi.probePS3).toHaveBeenCalledWith({
      ip_address: "192.168.1.115",
      ftp_port: 21,
    });
    expect(wrapper.get(".alert[role='status']").attributes("data-type")).toBe(
      "success",
    );
    expect(
      (field(wrapper, "settings.ps3-user").element as HTMLInputElement).value,
    ).toBe("00000002");
  });

  it("warns when nothing answers", async () => {
    vi.mocked(deviceApi.probePS3).mockResolvedValue({
      data: { reachable: false, is_ftp: false, users: [] },
    } as never);
    const wrapper = mountDialog();
    await field(wrapper, "settings.ps3-ip-address").setValue("192.168.1.9");

    await wrapper.get("[data-icon='mdi-lan-connect']").trigger("click");
    await flushPromises();

    expect(wrapper.get(".alert[role='status']").text()).toBe(
      "settings.ps3-test-unreachable",
    );
  });
});
