import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { defineComponent, nextTick, ref, type Ref } from "vue";
import romApi from "@/services/api/rom";
import { useReadingProgress } from "./index";

vi.mock("@/services/api/rom", () => ({
  default: { getFileProgress: vi.fn(), updateFileProgress: vi.fn() },
}));

const getFileProgress = vi.mocked(romApi.getFileProgress);
const updateFileProgress = vi.mocked(romApi.updateFileProgress);

// scrollable height is 500, so scrollTop 250 is a 0.5 fraction.
function makeScrollEl(scrollTop: number): HTMLElement {
  return { scrollTop, scrollHeight: 1000, clientHeight: 500 } as HTMLElement;
}

/** Runs the composable inside a real component so watch/unmount hooks apply. */
function withComposable(
  romId: Ref<number>,
  fileId: Ref<number | null>,
  scrollEl: Ref<HTMLElement | null>,
) {
  let api!: ReturnType<typeof useReadingProgress>;
  const wrapper = mount(
    defineComponent({
      setup() {
        api = useReadingProgress(romId, fileId, scrollEl);
        return () => null;
      },
    }),
  );
  return { api, wrapper };
}

beforeEach(() => {
  vi.useFakeTimers();
  getFileProgress.mockReset();
  updateFileProgress.mockReset();
  getFileProgress.mockResolvedValue({ data: { progress: 0 } } as never);
  updateFileProgress.mockResolvedValue({ data: {} } as never);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("useReadingProgress", () => {
  it("saves the outgoing document's position when the tracked file changes", async () => {
    const fileId = ref<number | null>(10);
    const { api } = withComposable(ref(1), fileId, ref(makeScrollEl(250)));

    api.onScroll();
    // Switch documents inside the debounce window, before the timer fires.
    fileId.value = 11;
    await nextTick();

    expect(updateFileProgress).toHaveBeenCalledTimes(1);
    expect(updateFileProgress).toHaveBeenCalledWith({
      romId: 1,
      fileId: 10,
      data: { progress: 0.5, finished: false },
    });
  });

  it("saves a pending position on unmount", async () => {
    const { api, wrapper } = withComposable(
      ref(3),
      ref<number | null>(20),
      ref(makeScrollEl(500)),
    );

    api.onScroll();
    wrapper.unmount();

    expect(updateFileProgress).toHaveBeenCalledWith({
      romId: 3,
      fileId: 20,
      data: { progress: 1, finished: true },
    });
  });

  it("does not re-send a position that was already saved", async () => {
    const { api } = withComposable(
      ref(1),
      ref<number | null>(10),
      ref(makeScrollEl(250)),
    );

    api.onScroll();
    vi.advanceTimersByTime(1000);
    expect(updateFileProgress).toHaveBeenCalledTimes(1);

    // A second debounce window with no further scrolling must stay quiet.
    vi.advanceTimersByTime(1000);
    expect(updateFileProgress).toHaveBeenCalledTimes(1);
  });
});
