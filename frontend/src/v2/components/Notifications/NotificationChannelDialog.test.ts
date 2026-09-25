import { RCheckbox, RComboboxField, RSelect } from "@v2/lib";
import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick } from "vue";
import type { NotificationChannelSchema } from "@/__generated__";
import storePermissions from "@/stores/permissions";
import {
  makeAppriseService,
  makeChannel,
} from "@/v2/utils/notificationChannels.fixtures";
import NotificationChannelDialog from "./NotificationChannelDialog.vue";

const api = vi.hoisted(() => ({
  create: vi.fn(),
  update: vi.fn(),
  getAppriseServices: vi.fn(),
  parseAppriseUrl: vi.fn(),
}));

vi.mock("@/services/api/notificationChannel", () => ({ default: api }));
vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key, locale: { value: "en_US" } }),
}));

function channel(
  overrides: Partial<NotificationChannelSchema> = {},
): NotificationChannelSchema {
  return makeChannel({
    id: 4,
    type: "webhook",
    name: "Hook",
    topics: ["scans"],
    target: "https://hooks.example.com/…oken",
    service: null,
    service_name: null,
    fields: null,
    stored_secrets: null,
    has_secret: true,
    ...overrides,
  });
}

const WEBHOOK_PLACEHOLDER = '[placeholder="https://example.com/hooks/romm"]';

async function open(
  existing: NotificationChannelSchema | null = null,
  { admin = false } = {},
) {
  const permissions = storePermissions();
  permissions.isAdmin = admin;
  permissions.hydrated = true;
  const wrapper = mount(NotificationChannelDialog, {
    props: { modelValue: false, channel: existing },
    attachTo: document.body,
    global: {
      stubs: {
        RDialog: defineComponent({
          props: { modelValue: { type: Boolean, default: false } },
          template: `<div v-if="modelValue"><slot name="header" /><slot name="content" /><slot name="footer" /></div>`,
        }),
      },
    },
  });
  await wrapper.setProps({ modelValue: true });
  await flushPromises();
  return wrapper;
}

type Wrapper = Awaited<ReturnType<typeof open>>;

function input(wrapper: Wrapper, selector: string) {
  return wrapper.find<HTMLInputElement>(`input${selector}`);
}

async function pick(wrapper: Wrapper, kind: string) {
  wrapper.findAllComponents(RSelect)[0].vm.$emit("update:modelValue", kind);
  await nextTick();
}

function textField(wrapper: Wrapper, label: string) {
  return wrapper
    .findAll(".r-text-field")
    .find((field) => field.text().includes(label))
    ?.find<HTMLInputElement>("input");
}

async function save(wrapper: Wrapper) {
  await wrapper
    .findAll("button")
    .find((b) => b.text() === "common.save")
    ?.trigger("click");
  await flushPromises();
}

describe("NotificationChannelDialog", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
    api.getAppriseServices.mockResolvedValue({ data: [makeAppriseService()] });
  });

  it("creates a webhook that forwards every topic", async () => {
    api.create.mockResolvedValue({ data: channel() });
    const wrapper = await open();

    await wrapper.findAll("input.r-text-field__input")[0].setValue(" Hook ");
    await input(wrapper, WEBHOOK_PLACEHOLDER).setValue(
      " https://hooks.example.com/romm ",
    );
    await input(wrapper, '[type="password"]').setValue("s3cret");
    await save(wrapper);

    expect(api.create).toHaveBeenCalledWith({
      type: "webhook",
      name: "Hook",
      url: "https://hooks.example.com/romm",
      secret: "s3cret",
      min_level: "info",
      topics: null,
    });
    expect(wrapper.emitted("saved")?.[0]).toEqual([channel()]);
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual([false]);
    wrapper.unmount();
  });

  it("sends nothing for a URL that isn't http", async () => {
    const wrapper = await open();

    await wrapper.findAll("input.r-text-field__input")[0].setValue("Hook");
    await input(wrapper, WEBHOOK_PLACEHOLDER).setValue("ftp://example.com");
    await save(wrapper);

    expect(api.create).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("builds an admin's Apprise channel from the service's fields", async () => {
    api.create.mockResolvedValue({ data: channel({ type: "apprise" }) });
    const wrapper = await open(null, { admin: true });

    await pick(wrapper, "apprise:ntfy");
    await wrapper.findAll("input.r-text-field__input")[0].setValue("Phone");
    await textField(wrapper, "notifications.channel-field-host")?.setValue(
      "ntfy.example.com",
    );
    wrapper
      .findComponent(RComboboxField)
      .vm.$emit("update:modelValue", ["romm"]);
    await nextTick();
    await save(wrapper);

    expect(api.create).toHaveBeenCalledWith({
      type: "apprise",
      name: "Phone",
      service: "ntfy",
      fields: {
        schema: "ntfys",
        host: "ntfy.example.com",
        targets: ["romm"],
        image: true,
        priority: "default",
      },
      min_level: "info",
      topics: null,
    });
    wrapper.unmount();
  });

  it("asks for a required list before saving", async () => {
    const wrapper = await open(null, { admin: true });

    await pick(wrapper, "apprise:ntfy");
    await wrapper.findAll("input.r-text-field__input")[0].setValue("Phone");
    await save(wrapper);

    expect(api.create).not.toHaveBeenCalled();
    expect(wrapper.find(".r-combobox-field").text()).toContain(
      "common.required",
    );
    wrapper.unmount();
  });

  const ntfyChannel = () =>
    channel({
      type: "apprise",
      service: "ntfy",
      service_name: "ntfy",
      fields: { host: "ntfy.example.com", targets: ["romm"] },
      stored_secrets: ["token"],
      has_secret: false,
    });
  async function paste(wrapper: Wrapper, url: string) {
    await textField(wrapper, "notifications.channel-paste-url")?.setValue(url);
    // Past the field's debounce.
    await new Promise((resolve) => setTimeout(resolve, 450));
    await flushPromises();
  }

  it("fills the fields in as soon as a URL is pasted", async () => {
    api.create.mockResolvedValue({ data: channel({ type: "apprise" }) });
    api.parseAppriseUrl.mockResolvedValue({
      data: {
        service: "ntfy",
        fields: { host: "ntfy.example.com", port: 8080, targets: ["romm"] },
      },
    });
    const wrapper = await open(null, { admin: true });

    await pick(wrapper, "apprise:ntfy");
    await wrapper.findAll("input.r-text-field__input")[0].setValue("Phone");
    await paste(wrapper, "ntfys://ntfy.example.com:8080/romm");

    const pasted = textField(wrapper, "notifications.channel-paste-url");
    expect(pasted?.element.value).toBe("ntfys://ntfy.example.com:8080/romm");
    expect(wrapper.text()).toContain("notifications.channel-paste-filled");
    expect(wrapper.findAll(".r-v2-apprise-field--filled")).toHaveLength(3);
    await save(wrapper);

    expect(api.parseAppriseUrl).toHaveBeenCalledWith(
      "ntfys://ntfy.example.com:8080/romm",
    );
    expect(api.create.mock.calls[0][0].fields).toMatchObject({
      host: "ntfy.example.com",
      port: 8080,
      targets: ["romm"],
    });
    wrapper.unmount();
  });

  it("says why it can't read a pasted URL", async () => {
    api.parseAppriseUrl.mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: "Apprise can't read this URL" } },
    });
    const wrapper = await open(null, { admin: true });

    await pick(wrapper, "apprise:ntfy");
    await paste(wrapper, "nowhere://romm");

    expect(wrapper.text()).toContain("Apprise can't read this URL");
    wrapper.unmount();
  });

  it("moves a new channel to the service a pasted URL is for", async () => {
    const discord = makeAppriseService({
      id: "discord",
      name: "Discord",
      fields: [],
    });
    api.getAppriseServices.mockResolvedValue({
      data: [makeAppriseService(), discord],
    });
    api.parseAppriseUrl.mockResolvedValue({
      data: { service: "discord", fields: {} },
    });
    const wrapper = await open(null, { admin: true });

    await pick(wrapper, "apprise:ntfy");
    await paste(wrapper, "https://discord.com/api/webhooks/1/token");

    expect(wrapper.findAllComponents(RSelect)[0].props("modelValue")).toBe(
      "apprise:discord",
    );
    wrapper.unmount();
  });

  it("keeps an edited channel on its service whatever URL is pasted", async () => {
    api.parseAppriseUrl.mockResolvedValue({
      data: { service: "discord", fields: {} },
    });
    api.getAppriseServices.mockResolvedValue({
      data: [
        makeAppriseService(),
        makeAppriseService({ id: "discord", name: "Discord", fields: [] }),
      ],
    });
    const wrapper = await open(ntfyChannel(), { admin: true });

    await paste(wrapper, "https://discord.com/api/webhooks/1/token");

    expect(wrapper.text()).toContain(
      "notifications.channel-paste-other-service",
    );
    wrapper.unmount();
  });

  const discord = () => {
    const secret = {
      type: "string" as const,
      required: true,
      private: true,
      advanced: false,
      default: null,
      values: null,
      min: null,
      max: null,
    };
    return makeAppriseService({
      id: "discord",
      name: "Discord",
      url_fields: ["webhook_id", "webhook_token"],
      fields: [
        {
          ...secret,
          key: "botname",
          label: "Bot Name",
          required: false,
          private: false,
        },
        { ...secret, key: "webhook_id", label: "Webhook ID" },
        { ...secret, key: "webhook_token", label: "Webhook Token" },
      ],
    });
  };

  it("sets a service with its own URL up from that URL alone", async () => {
    api.getAppriseServices.mockResolvedValue({
      data: [makeAppriseService(), discord()],
    });
    api.parseAppriseUrl.mockResolvedValue({
      data: {
        service: "discord",
        fields: { webhook_id: "1", webhook_token: "t" },
      },
    });
    api.create.mockResolvedValue({ data: channel({ type: "apprise" }) });
    const wrapper = await open(null, { admin: true });

    await pick(wrapper, "apprise:discord");
    expect(textField(wrapper, "Webhook ID")).toBeUndefined();
    await wrapper.findAll("input.r-text-field__input")[0].setValue("Alerts");
    await textField(wrapper, "notifications.channel-field-botname")?.setValue(
      "RomM",
    );
    // Saved before the pause that would read it.
    await textField(wrapper, "notifications.channel-service-url")?.setValue(
      "https://discord.com/api/webhooks/1/t",
    );
    await save(wrapper);

    expect(api.parseAppriseUrl).toHaveBeenCalledWith(
      "https://discord.com/api/webhooks/1/t",
    );
    expect(api.create.mock.calls[0][0]).toMatchObject({
      service: "discord",
      fields: { botname: "RomM", webhook_id: "1", webhook_token: "t" },
    });
    wrapper.unmount();
  });

  it("needs the URL of a service set up from one", async () => {
    api.getAppriseServices.mockResolvedValue({ data: [discord()] });
    const wrapper = await open(null, { admin: true });

    await pick(wrapper, "apprise:discord");
    await wrapper.findAll("input.r-text-field__input")[0].setValue("Alerts");
    await save(wrapper);

    expect(api.create).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("offers Apprise's services to admins only", async () => {
    const kinds = async (admin: boolean) => {
      const wrapper = await open(null, { admin });
      const items = wrapper.findAllComponents(RSelect)[0].props("items") as {
        value: string;
      }[];
      wrapper.unmount();
      return items.map((item) => item.value);
    };

    expect(await kinds(false)).toEqual(["webhook", "email"]);
    expect(await kinds(true)).toEqual(["webhook", "email", "apprise:ntfy"]);
    expect(api.getAppriseServices).toHaveBeenCalledOnce();
  });

  it("keeps the URL and secret an edit leaves blank", async () => {
    api.update.mockResolvedValue({ data: channel() });
    const wrapper = await open(channel());

    await save(wrapper);

    expect(api.update).toHaveBeenCalledWith(4, {
      name: "Hook",
      min_level: "info",
      topics: ["scans"],
    });
    wrapper.unmount();
  });

  it("keeps the Apprise secrets an edit leaves blank", async () => {
    api.update.mockResolvedValue({ data: channel({ type: "apprise" }) });
    const wrapper = await open(ntfyChannel(), { admin: true });

    expect(
      textField(wrapper, "notifications.channel-field-token")?.attributes(
        "type",
      ),
    ).toBe("password");
    await save(wrapper);

    // The token is left out, so the channel keeps it.
    expect(api.update).toHaveBeenCalledWith(4, {
      name: "Hook",
      min_level: "info",
      topics: ["scans"],
      fields: {
        schema: "ntfys",
        host: "ntfy.example.com",
        targets: ["romm"],
        image: true,
        priority: "default",
      },
    });
    wrapper.unmount();
  });

  it("removes a stored Apprise secret when asked to", async () => {
    api.update.mockResolvedValue({ data: channel({ type: "apprise" }) });
    const wrapper = await open(ntfyChannel(), { admin: true });

    wrapper
      .findAllComponents(RCheckbox)
      .find(
        (box) => box.props("label") === "notifications.channel-secret-remove",
      )
      ?.vm.$emit("update:modelValue", true);
    await save(wrapper);

    expect(api.update.mock.calls[0][1].fields).toMatchObject({ token: "" });
    wrapper.unmount();
  });

  it("drops the secret when asked to", async () => {
    api.update.mockResolvedValue({ data: channel({ has_secret: false }) });
    const wrapper = await open(channel());

    await wrapper.find('input[type="checkbox"]').setValue(true);
    await save(wrapper);

    expect(api.update.mock.calls[0][1]).toMatchObject({ secret: "" });
    wrapper.unmount();
  });

  it("moves an email channel to a new address", async () => {
    api.update.mockResolvedValue({ data: channel() });
    const wrapper = await open(
      channel({
        type: "email",
        target: "a@example.com",
        has_secret: false,
      }),
    );

    await input(wrapper, '[type="email"]').setValue("b@example.com");
    await save(wrapper);

    expect(api.update).toHaveBeenCalledWith(4, {
      name: "Hook",
      min_level: "info",
      topics: ["scans"],
      address: "b@example.com",
    });
    wrapper.unmount();
  });

  it("shows why the server refused and stays open", async () => {
    vi.spyOn(console, "error").mockImplementation(() => {});
    api.update.mockRejectedValue({
      isAxiosError: true,
      response: { data: { detail: "The URL must start with http://" } },
    });
    const wrapper = await open(channel());

    await save(wrapper);

    expect(wrapper.text()).toContain("The URL must start with http://");
    expect(wrapper.emitted("saved")).toBeUndefined();
    wrapper.unmount();
  });
});
