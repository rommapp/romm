import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";
import SteamLibrarySection from "./SteamLibrarySection.vue";

const STEAM_ID = "76561197960287930";

const confirm = vi.fn();
const assign = vi.fn();
const snackbar = { info: vi.fn(), error: vi.fn() };

vi.mock("vue-i18n");
vi.mock("@/services/api/user", () => ({
  default: {
    startSteamLogin: vi.fn(),
    unlinkSteamAccount: vi.fn(),
    syncSteamLibrary: vi.fn(),
    fetchSteamLibrary: vi.fn(),
  },
}));
vi.mock("@/composables/useSnackbar", () => ({ useSnackbar: () => snackbar }));
vi.mock("@/composables/useConfirm", () => ({ useConfirm: () => confirm }));
vi.mock("@/composables/useSocketEvent", () => ({ useSocketEvent: vi.fn() }));
const routerReplace = vi.fn();
let routeQuery: Record<string, string> = {};
vi.mock("vue-router", () => ({
  useRoute: () => ({ fullPath: "/settings/user/1", query: routeQuery }),
  useRouter: () => ({ replace: routerReplace }),
}));

function mountSection() {
  return mount(SteamLibrarySection, {
    global: {
      stubs: {
        RBtn: {
          props: { disabled: { type: Boolean, default: false } },
          emits: ["click"],
          template: `<button :disabled="disabled" @click="$emit('click')"><slot /></button>`,
        },
        RTag: { template: `<span class="tag"><slot /></span>` },
        RTextField: {
          props: { modelValue: { type: String, default: "" } },
          emits: ["update:modelValue"],
          template: `<input :value="modelValue" @input="$emit('update:modelValue', $event.target.value)" />`,
        },
        RIcon: true,
      },
    },
  });
}

describe("SteamLibrarySection", () => {
  beforeEach(() => {
    vi.stubGlobal("location", { ...window.location, assign });
    routeQuery = {};
    vi.mocked(userApi.fetchSteamLibrary).mockResolvedValue({
      data: [220, 400],
    } as never);
    vi.mocked(userApi.syncSteamLibrary).mockResolvedValue({} as never);
  });

  it("reports a sign-in Steam refused and clears it from the url", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1 }));
    routeQuery = { steam_error: "Steam could not confirm the sign-in" };

    mountSection();
    await flushPromises();

    expect(snackbar.error).toHaveBeenCalledOnce();
    expect(routerReplace).toHaveBeenCalledWith({ query: {} });
  });

  it("says nothing when no sign-in just happened", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1 }));

    mountSection();
    await flushPromises();

    expect(snackbar.error).not.toHaveBeenCalled();
    expect(routerReplace).not.toHaveBeenCalled();
  });

  it("hands the browser to Steam to sign in", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1 }));
    vi.mocked(userApi.startSteamLogin).mockResolvedValue({
      data: { url: "https://steamcommunity.com/openid/login?openid.mode=x" },
    } as never);
    const wrapper = mountSection();

    await wrapper.get("button").trigger("click");
    await flushPromises();

    expect(userApi.startSteamLogin).toHaveBeenCalledExactlyOnceWith({
      id: 1,
      next: "/settings/user/1",
    });
    expect(assign).toHaveBeenCalledExactlyOnceWith(
      "https://steamcommunity.com/openid/login?openid.mode=x",
    );
  });

  it("stays put when the sign-in cannot be started", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1 }));
    vi.mocked(userApi.startSteamLogin).mockRejectedValue(new Error("nope"));
    const wrapper = mountSection();

    await wrapper.get("button").trigger("click");
    await flushPromises();

    expect(assign).not.toHaveBeenCalled();
    expect(snackbar.error).toHaveBeenCalledOnce();
  });

  it("shows how many games the linked account owns", async () => {
    storeAuth().setCurrentUser(
      userFixture({ id: 1, steam_id: STEAM_ID, steam_persona_name: "Gabe" }),
    );
    const wrapper = mountSection();
    await flushPromises();

    expect(userApi.fetchSteamLibrary).toHaveBeenCalledWith({ id: 1 });
    expect(wrapper.text()).toContain("settings.steam-owned-count");
  });

  it("ignores a second Sync press while one is in flight", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1, steam_id: STEAM_ID }));
    let release!: () => void;
    vi.mocked(userApi.syncSteamLibrary).mockReturnValueOnce(
      new Promise<never>((resolve) => {
        release = resolve as () => void;
      }),
    );
    const wrapper = mountSection();
    await flushPromises();
    const syncBtn = wrapper.findAll("button")[0]!;

    await syncBtn.trigger("click");
    await syncBtn.trigger("click");
    release();
    await flushPromises();

    expect(userApi.syncSteamLibrary).toHaveBeenCalledExactlyOnceWith({ id: 1 });
  });

  it("unlinks only once confirmed", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1, steam_id: STEAM_ID }));
    vi.mocked(userApi.unlinkSteamAccount).mockResolvedValue({
      data: userFixture({ id: 1 }),
    } as never);
    const wrapper = mountSection();
    const unlink = () => wrapper.findAll("button")[1]!.trigger("click");

    confirm.mockResolvedValueOnce(false);
    await unlink();
    await flushPromises();
    expect(userApi.unlinkSteamAccount).not.toHaveBeenCalled();

    confirm.mockResolvedValueOnce(true);
    await unlink();
    await flushPromises();
    expect(userApi.unlinkSteamAccount).toHaveBeenCalledExactlyOnceWith({
      id: 1,
    });
    expect(storeAuth().user?.steam_id).toBeUndefined();
  });
});
