import { afterEach, describe, expect, it } from "vitest";
import { installIOSFullscreenShim } from "./playerFullscreen";

// happy-dom defines these on Navigator.prototype, so the overrides below are
// own properties we delete again rather than descriptors we restore.
const PATCHED_NAV_KEYS = ["platform", "maxTouchPoints"] as const;

function setNav(platform: string, maxTouchPoints: number) {
  Object.defineProperty(navigator, "platform", {
    value: platform,
    configurable: true,
  });
  Object.defineProperty(navigator, "maxTouchPoints", {
    value: maxTouchPoints,
    configurable: true,
  });
}

// The shim keys off iPadOS 13+, which reports as MacIntel with touch support.
function pretendIOS() {
  setNav("MacIntel", 5);
}

function pretendDesktop() {
  setNav("Win32", 0);
}

afterEach(() => {
  PATCHED_NAV_KEYS.forEach((key) => Reflect.deleteProperty(navigator, key));
  document.body.innerHTML = "";
});

describe("installIOSFullscreenShim", () => {
  it("leaves the Fullscreen API untouched off iOS", () => {
    pretendDesktop();
    const before = HTMLElement.prototype.requestFullscreen;

    const dispose = installIOSFullscreenShim();

    expect(HTMLElement.prototype.requestFullscreen).toBe(before);
    dispose();
  });

  it("reports fullscreen as available once installed", () => {
    pretendIOS();
    const dispose = installIOSFullscreenShim();

    expect(document.fullscreenEnabled).toBe(true);
    expect(document.fullscreenElement).toBeNull();

    dispose();
  });

  it("marks the element and fires fullscreenchange on enter", async () => {
    pretendIOS();
    const dispose = installIOSFullscreenShim();
    const el = document.createElement("div");
    document.body.appendChild(el);

    let changes = 0;
    document.addEventListener("fullscreenchange", () => changes++);

    await el.requestFullscreen();

    expect(el.hasAttribute("data-ios-fullscreen-active")).toBe(true);
    expect(document.fullscreenElement).toBe(el);
    expect(changes).toBe(1);

    dispose();
  });

  it("clears the element on exit", async () => {
    pretendIOS();
    const dispose = installIOSFullscreenShim();
    const el = document.createElement("div");
    document.body.appendChild(el);

    await el.requestFullscreen();
    await document.exitFullscreen();

    expect(el.hasAttribute("data-ios-fullscreen-active")).toBe(false);
    expect(document.fullscreenElement).toBeNull();

    dispose();
  });

  it("restores the patched API and removes its stylesheet on dispose", async () => {
    pretendIOS();
    const before = HTMLElement.prototype.requestFullscreen;
    const styleCount = document.head.querySelectorAll("style").length;

    const dispose = installIOSFullscreenShim();
    const el = document.createElement("div");
    document.body.appendChild(el);
    await el.requestFullscreen();
    dispose();

    expect(HTMLElement.prototype.requestFullscreen).toBe(before);
    expect(document.head.querySelectorAll("style")).toHaveLength(styleCount);
    expect(el.hasAttribute("data-ios-fullscreen-active")).toBe(false);
  });
});
