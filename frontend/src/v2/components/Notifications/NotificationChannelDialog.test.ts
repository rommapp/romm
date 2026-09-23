import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick } from "vue";
import type { NotificationChannelSchema } from "@/__generated__";
import NotificationChannelDialog from "./NotificationChannelDialog.vue";

const api = vi.hoisted(() => ({ create: vi.fn(), update: vi.fn() }));

vi.mock("@/services/api/notificationChannel", () => ({ default: api }));
vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function channel(
  overrides: Partial<NotificationChannelSchema> = {},
): NotificationChannelSchema {
  return {
    id: 4,
    type: "webhook",
    name: "Hook",
    enabled: true,
    min_level: "info",
    topics: ["scans"],
    target: "https://hooks.example.com/…oken",
    format: "json",
    has_secret: true,
    confirmed: true,
    last_delivered_at: null,
    last_error: null,
    consecutive_failures: 0,
    created_at: "2026-09-23T12:00:00+00:00",
    ...overrides,
  };
}

async function open(existing: NotificationChannelSchema | null = null) {
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
  await nextTick();
  return wrapper;
}

type Wrapper = Awaited<ReturnType<typeof open>>;

function input(wrapper: Wrapper, selector: string) {
  return wrapper.find<HTMLInputElement>(`input${selector}`);
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
  });

  it("creates a JSON webhook that forwards every topic", async () => {
    api.create.mockResolvedValue({ data: channel() });
    const wrapper = await open();

    await wrapper.findAll("input.r-text-field__input")[0].setValue(" Hook ");
    await input(
      wrapper,
      '[placeholder="https://example.com/hooks/romm"]',
    ).setValue(" https://hooks.example.com/romm ");
    await input(wrapper, '[type="password"]').setValue("s3cret");
    await save(wrapper);

    expect(api.create).toHaveBeenCalledWith({
      type: "webhook",
      name: "Hook",
      url: "https://hooks.example.com/romm",
      format: "json",
      secret: "s3cret",
      min_level: "info",
      topics: null,
    });
    expect(wrapper.emitted("saved")?.[0]).toEqual([channel(), true]);
    expect(wrapper.emitted("update:modelValue")?.at(-1)).toEqual([false]);
    wrapper.unmount();
  });

  it("sends nothing for a URL that isn't http", async () => {
    const wrapper = await open();

    await wrapper.findAll("input.r-text-field__input")[0].setValue("Hook");
    await input(
      wrapper,
      '[placeholder="https://example.com/hooks/romm"]',
    ).setValue("ftp://example.com");
    await save(wrapper);

    expect(api.create).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("keeps the URL and secret an edit leaves blank", async () => {
    api.update.mockResolvedValue({ data: channel() });
    const wrapper = await open(channel());

    await save(wrapper);

    expect(api.update).toHaveBeenCalledWith(4, {
      name: "Hook",
      min_level: "info",
      topics: ["scans"],
      format: "json",
    });
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
        format: null,
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
      response: { data: { detail: "The URL must start with http://" } },
    });
    const wrapper = await open(channel());

    await save(wrapper);

    expect(wrapper.text()).toContain("The URL must start with http://");
    expect(wrapper.emitted("saved")).toBeUndefined();
    wrapper.unmount();
  });
});
