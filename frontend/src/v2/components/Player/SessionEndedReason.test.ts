import { mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import SessionEndedReason from "./SessionEndedReason.vue";

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

describe("SessionEndedReason", () => {
  it("shows the reason under its label", () => {
    const wrapper = mount(SessionEndedReason, {
      props: { reason: "Maintenance" },
    });

    expect(wrapper.text()).toContain("play.session-ended-reason-label");
    expect(wrapper.text()).toContain("Maintenance");
  });
});
