import { flushPromises, mount } from "@vue/test-utils";
import { beforeEach, describe, expect, it, vi } from "vitest";
import userApi from "@/services/api/user";
import storeAuth from "@/stores/auth";
import { userFixture } from "@/utils/user.fixtures";
import SteamLibrarySection from "./SteamLibrarySection.vue";

const STEAM_ID = "76561197960287930";

const confirm = vi.fn();
const snackbar = { info: vi.fn(), error: vi.fn() };

vi.mock("vue-i18n");
vi.mock("@/services/api/user", () => ({
  default: {
    linkSteamAccount: vi.fn(),
    unlinkSteamAccount: vi.fn(),
    syncSteamLibrary: vi.fn(),
    fetchSteamLibrary: vi.fn(),
  },
}));
vi.mock("@/composables/useSnackbar", () => ({ useSnackbar: () => snackbar }));
vi.mock("@/composables/useConfirm", () => ({ useConfirm: () => confirm }));
vi.mock("@/composables/useSocketEvent", () => ({ useSocketEvent: vi.fn() }));

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
    vi.mocked(userApi.fetchSteamLibrary).mockResolvedValue({
      data: [220, 400],
    } as never);
    vi.mocked(userApi.syncSteamLibrary).mockResolvedValue({} as never);
  });

  it("links the typed profile, then starts a sync", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1 }));
    vi.mocked(userApi.linkSteamAccount).mockResolvedValue({
      data: userFixture({
        id: 1,
        steam_id: STEAM_ID,
        steam_persona_name: "Gabe",
      }),
    } as never);
    const wrapper = mountSection();

    await wrapper.get("input").setValue("  gabelogannewell ");
    await wrapper.get("button").trigger("click");
    await flushPromises();

    expect(userApi.linkSteamAccount).toHaveBeenCalledExactlyOnceWith({
      id: 1,
      profile: "gabelogannewell",
    });
    expect(userApi.syncSteamLibrary).toHaveBeenCalledExactlyOnceWith({ id: 1 });
    expect(storeAuth().user?.steam_id).toBe(STEAM_ID);
  });

  it("keeps the field and skips the sync when Steam rejects the profile", async () => {
    storeAuth().setCurrentUser(userFixture({ id: 1 }));
    vi.mocked(userApi.linkSteamAccount).mockRejectedValue(new Error("nope"));
    const wrapper = mountSection();

    await wrapper.get("input").setValue("nobody");
    await wrapper.get("button").trigger("click");
    await flushPromises();

    expect(userApi.syncSteamLibrary).not.toHaveBeenCalled();
    expect(snackbar.error).toHaveBeenCalledOnce();
    expect(wrapper.get("input").element.value).toBe("nobody");
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
