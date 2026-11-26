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
  window.dispatchEvent(
    new PointerEvent("pointerdown", { pointerType: "touch" }),
  );
}

function mouse(type: "pointerdown" | "pointermove") {
  window.dispatchEvent(new PointerEvent(type, { pointerType: "mouse" }));
}

describe("isNavigationKey", () => {
  it.each([
    "ArrowUp",
    "Tab",
    "Enter",
    " ",
    "Escape",
    "Home",
    "End",
    "PageUp",
    "PageDown",
  ])("counts %j as keyboard navigation", async (key) => {
    const { isNavigationKey } = await import("./index");
    expect(isNavigationKey(key)).toBe(true);
  });

  it.each(["a", "Shift", "Control", "F5"])("ignores %j", async (key) => {
    const { isNavigationKey } = await import("./index");
    expect(isNavigationKey(key)).toBe(false);
  });
});

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
    window.dispatchEvent(new MouseEvent("mousedown"));
    window.dispatchEvent(new MouseEvent("mousemove"));
    window.dispatchEvent(
      new PointerEvent("pointermove", { pointerType: "touch" }),
    );

    expect(modality.value).toBe("touch");
  });

  it("follows a real mouse right after a tap", async () => {
    const { modality } = await loadFresh();

    tap();
    mouse("pointermove");

    expect(modality.value).toBe("mouse");
  });

  it("switches back to the mouse from a gamepad on a click only", async () => {
    const { modality, setModality } = await loadFresh();

    setModality("pad");
    mouse("pointerdown");

    expect(modality.value).toBe("mouse");
  });

  it("keeps a gamepad from being nudged out by mouse movement", async () => {
    const { modality, setModality } = await loadFresh();

    setModality("pad");
    mouse("pointermove");

    expect(modality.value).toBe("pad");
  });

  it("leaves script-dispatched keys to whoever dispatched them", async () => {
    const { modality, setModality } = await loadFresh();

    setModality("pad");
    window.dispatchEvent(new KeyboardEvent("keydown", { key: "ArrowDown" }));

    expect(modality.value).toBe("pad");
  });

  it("ignores every input while pinned, and resumes tracking once unpinned", async () => {
    const { modality, pin } = await loadFresh();

    pin("key");
    expect(document.documentElement.dataset.input).toBe("key");

    tap();
    window.dispatchEvent(new Event("gamepadconnected"));
    expect(modality.value).toBe("key");

    pin(null);
    tap();
    expect(modality.value).toBe("touch");
  });
});
