import { mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ref } from "vue";
import type { SimpleRom } from "@/stores/roms";
import GameActionBtn from "./GameActionBtn.vue";

const play = vi.fn();

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

vi.mock("@/v2/composables/useBreakpoint", () => ({
  useBreakpoint: () => ({ smAndDown: ref(false) }),
}));

vi.mock("@/v2/composables/useGameActions", () => ({
  GAME_ACTIONS_KEY: Symbol("game-actions"),
  useGameActions: () => ({
    play,
    playPath: (player: string) =>
      player === "stream" ? "/rom/1/stream" : "/rom/1/ejs",
    streamActionLabel: { value: "rom.stream" },
    isFavorited: { value: false },
    currentStatusKey: { value: null },
  }),
}));

type Props = InstanceType<typeof GameActionBtn>["$props"];

function mountBtn(props: Partial<Props> = {}) {
  return mount(GameActionBtn, {
    props: { rom: { id: 1 } as SimpleRom, action: "play", ...props },
    global: { stubs: { RIcon: true, RTooltip: true } },
  });
}

// Dispatches a real click and reports whether the component prevented it,
// then prevents it anyway so jsdom never tries to follow the href.
function click(el: Element, init: MouseEventInit = {}): boolean {
  let prevented = false;
  el.addEventListener(
    "click",
    (e) => {
      prevented = e.defaultPrevented;
      e.preventDefault();
    },
    { once: true },
  );
  el.dispatchEvent(
    new MouseEvent("click", { bubbles: true, cancelable: true, ...init }),
  );
  return prevented;
}

beforeEach(() => {
  play.mockClear();
});

describe("GameActionBtn: launch links", () => {
  it("stays a button unless asked to link", () => {
    const wrapper = mountBtn();

    expect(wrapper.find("button.r-v2-game-btn").exists()).toBe(true);
    expect(wrapper.find("a").exists()).toBe(false);
  });

  it("links play and stream to their player documents", () => {
    const playLink = mountBtn({ link: true }).get("a.r-v2-game-btn");
    const streamLink = mountBtn({ link: true, action: "stream" }).get(
      "a.r-v2-game-btn",
    );

    expect(playLink.attributes("href")).toBe("/rom/1/ejs");
    expect(playLink.attributes("type")).toBeUndefined();
    expect(streamLink.attributes("href")).toBe("/rom/1/stream");
  });

  it("launches in place on a plain click", () => {
    const wrapper = mountBtn({ link: true });

    expect(click(wrapper.get("a").element)).toBe(true);
    expect(play).toHaveBeenCalledWith("local");
  });

  it("leaves a modified click to the browser so the player opens elsewhere", () => {
    const wrapper = mountBtn({ link: true, action: "stream" });

    expect(click(wrapper.get("a").element, { ctrlKey: true })).toBe(false);
    expect(play).not.toHaveBeenCalled();
  });

  it("keeps the other actions as buttons even when asked to link", () => {
    const wrapper = mountBtn({ link: true, action: "download" });

    expect(wrapper.find("button.r-v2-game-btn").exists()).toBe(true);
    expect(wrapper.find("a").exists()).toBe(false);
  });
});
