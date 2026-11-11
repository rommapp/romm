import { RouterLinkStub, shallowMount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ROUTES } from "@/plugins/routeNames";
import PlayerCountBadge from "./PlayerCountBadge.vue";

vi.mock("vue-i18n");

describe("PlayerCountBadge", () => {
  it("pivots to the playerCounts gallery search with the stored value", () => {
    const wrapper = shallowMount(PlayerCountBadge, {
      props: { value: " 1-4 " },
      global: { stubs: { RouterLink: RouterLinkStub, RIcon: true } },
    });

    expect(wrapper.findComponent(RouterLinkStub).props("to")).toEqual({
      name: ROUTES.SEARCH,
      query: { playerCounts: " 1-4 " },
    });
  });
});
