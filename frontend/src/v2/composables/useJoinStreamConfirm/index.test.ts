import { beforeEach, describe, expect, it, vi } from "vitest";
import { useJoinStreamConfirm } from "./index";

const push = vi.fn();
const confirmFn = vi.fn();

vi.mock("vue-i18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));
vi.mock("vue-router", () => ({
  useRouter: () => ({ push }),
}));
vi.mock("@/v2/composables/useConfirm", () => ({
  useConfirm: () => confirmFn,
}));

const target = { romId: 1, romName: "Chrono Trigger", hostUsername: "ada" };

describe("useJoinStreamConfirm", () => {
  beforeEach(() => {
    push.mockClear();
    confirmFn.mockClear();
  });

  it("does not navigate until the user confirms", async () => {
    confirmFn.mockResolvedValue(false);
    const { joinStream } = useJoinStreamConfirm();

    await joinStream(target);

    expect(push).not.toHaveBeenCalled();
  });

  it("navigates with the join intent once confirmed", async () => {
    confirmFn.mockResolvedValue(true);
    const { joinStream } = useJoinStreamConfirm();

    await joinStream(target);

    expect(push).toHaveBeenCalledWith("/rom/1/stream?join=1");
  });

  it("names the host in the confirmation", async () => {
    confirmFn.mockResolvedValue(false);
    const { joinStream } = useJoinStreamConfirm();

    await joinStream(target);

    expect(confirmFn.mock.calls[0][0].title).toBe("rom.confirm-join-title-of");
  });

  it("falls back to an unnamed prompt when the host is unknown", async () => {
    confirmFn.mockResolvedValue(false);
    const { joinStream } = useJoinStreamConfirm();

    await joinStream({ ...target, hostUsername: null });

    expect(confirmFn.mock.calls[0][0].title).toBe("rom.confirm-join-title");
  });
});
