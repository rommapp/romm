import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import Register from "./Register.vue";

const { registerUser } = vi.hoisted(() => ({ registerUser: vi.fn() }));

vi.mock("vue-i18n");

vi.mock("vue-router", () => ({
  useRoute: () => ({ query: { token: "invite-token" } }),
  useRouter: () => ({ push: vi.fn() }),
}));

vi.mock("@/services/api/user", () => ({ default: { registerUser } }));

vi.mock("@/stores/users", () => ({
  default: () => ({
    usernameRules: [(v: string) => !!v || "required"],
    emailRules: [(v: string) => /.+@.+\..+/.test(v) || "invalid email"],
    passwordRules: [(v: string) => !!v || "required"],
  }),
}));

vi.mock("@/v2/composables/useSnackbar", () => ({
  useSnackbar: () => ({ success: vi.fn(), error: vi.fn() }),
}));

function mountRegister() {
  return mount(Register, {
    global: {
      stubs: {
        AuthCard: { template: "<div><slot /></div>" },
        AuthBackLink: true,
      },
    },
  });
}

async function fill(
  wrapper: ReturnType<typeof mountRegister>,
  values: [string, string, string],
) {
  const inputs = wrapper.findAll("input");
  for (const [i, value] of values.entries()) await inputs[i]!.setValue(value);
}

describe("Register", () => {
  it("does not register while a field fails its rules", async () => {
    const wrapper = mountRegister();
    await fill(wrapper, ["player1", "not-an-email", "hunter22"]);

    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(registerUser).not.toHaveBeenCalled();
  });

  it("registers once every field passes", async () => {
    registerUser.mockResolvedValue({});
    const wrapper = mountRegister();
    await fill(wrapper, ["player1", "player1@example.com", "hunter22"]);

    await wrapper.get("form").trigger("submit");
    await flushPromises();

    expect(registerUser).toHaveBeenCalledWith(
      "player1",
      "player1@example.com",
      "hunter22",
      "invite-token",
    );
  });
});
