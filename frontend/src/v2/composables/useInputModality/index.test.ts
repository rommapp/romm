import { beforeEach, describe, expect, it, vi } from "vitest";

// The listeners and the modality ref are module-level singletons, so each test
// re-imports the module to install onto a clean window.
async function loadFresh() {
  vi.resetModules();
  const { useInputModality } = await import("./index");
  const hook = useInputModality();
  hook.install();
  return hook;
}

function tap() {
  window.dispatchEvent(new Event("touchstart"));
}

describe("useInputModality", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.setSystemTime(0);
  });

  it("tracks the last input device", async () => {
    const { modality } = await loadFresh();

    tap();
    expect(modality.value).toBe("touch");
    expect(document.documentElement.dataset.input).toBe("touch");
  });

  it("ignores the compatibility mouse events a tap fires", async () => {
    const { modality } = await loadFresh();

    tap();
    window.dispatchEvent(new Event("mousedown"));
    window.dispatchEvent(new Event("mousemove"));

    expect(modality.value).toBe("touch");
  });

  it("follows a real mouse once the tap window has passed", async () => {
    const { modality } = await loadFresh();

    tap();
    vi.advanceTimersByTime(1000);
    window.dispatchEvent(new Event("mousedown"));

    expect(modality.value).toBe("mouse");
  });

  it("keeps a gamepad from being nudged out by mouse movement", async () => {
    const { modality, setModality } = await loadFresh();

    setModality("pad");
    window.dispatchEvent(new Event("mousemove"));

    expect(modality.value).toBe("pad");
  });
});
