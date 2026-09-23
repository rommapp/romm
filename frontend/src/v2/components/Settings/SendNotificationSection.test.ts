import { flushPromises, mount } from "@vue/test-utils";
import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";
import SendNotificationSection from "./SendNotificationSection.vue";

const { create, fetchUsers, success } = vi.hoisted(() => ({
  create: vi.fn(),
  fetchUsers: vi.fn(),
  success: vi.fn(),
}));

vi.mock("@/services/api/notification", () => ({ default: { create } }));
vi.mock("@/services/api/user", () => ({ default: { fetchUsers } }));

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success, error: vi.fn() }),
}));

function mountSection() {
  return mount(SendNotificationSection, { attachTo: document.body });
}

async function fill(
  wrapper: ReturnType<typeof mountSection>,
  fields: { title?: string; body?: string; link?: string },
) {
  const [title, link] = wrapper.findAll("input.r-text-field__input");
  if (fields.title !== undefined) await title.setValue(fields.title);
  if (fields.body !== undefined) {
    await wrapper.find("textarea").setValue(fields.body);
  }
  if (fields.link !== undefined) await link.setValue(fields.link);
}

describe("SendNotificationSection", () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.resetAllMocks();
    fetchUsers.mockResolvedValue({ data: [] });
    create.mockResolvedValue({ data: [{ id: 1 }, { id: 2 }] });
  });

  it("broadcasts to everyone and clears the message", async () => {
    const wrapper = mountSection();
    await fill(wrapper, {
      title: "  Maintenance tonight ",
      body: "Down for 10 minutes",
      link: "/activity",
    });

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(create).toHaveBeenCalledWith({
      title: "Maintenance tonight",
      body: "Down for 10 minutes",
      link: "/activity",
      level: "info",
      icon: "mdi-bullhorn-outline",
      recipients: "all",
    });
    expect(success).toHaveBeenCalledOnce();
    expect(
      (wrapper.find("input.r-text-field__input").element as HTMLInputElement)
        .value,
    ).toBe("");
    wrapper.unmount();
  });

  it("sends nothing without a title", async () => {
    const wrapper = mountSection();

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(create).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it("refuses a link that leaves RomM", async () => {
    const wrapper = mountSection();
    await fill(wrapper, { title: "Hi", link: "https://example.com" });

    await wrapper.find("form").trigger("submit");
    await flushPromises();

    expect(create).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain("notifications.send-link-invalid");
    wrapper.unmount();
  });
});
