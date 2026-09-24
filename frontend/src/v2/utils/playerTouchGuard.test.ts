import { afterEach, describe, expect, it } from "vitest";
import { suppressVirtualGamepadZoneTouch } from "./playerTouchGuard";

afterEach(() => {
  document.body.innerHTML = "";
});

// Mirrors the production wiring: the handler listens on the stage root and
// touches bubble up from the EmulatorJS virtual-gamepad DOM inside it.
function mountStage(): { zone: HTMLElement; button: HTMLElement } {
  const stage = document.createElement("div");
  const zone = document.createElement("div");
  zone.classList.add("ejs_virtualGamepad_right");
  const button = document.createElement("div");
  button.classList.add("ejs_virtualGamepad_button");
  zone.appendChild(button);
  stage.appendChild(zone);
  document.body.appendChild(stage);
  stage.addEventListener("touchstart", suppressVirtualGamepadZoneTouch);
  return { zone, button };
}

function dispatchTouch(target: Element, type: string): Event {
  const event = new Event(type, { bubbles: true, cancelable: true });
  target.dispatchEvent(event);
  return event;
}

describe("suppressVirtualGamepadZoneTouch", () => {
  it("cancels touches that land on an empty gamepad zone", () => {
    const { zone } = mountStage();
    expect(dispatchTouch(zone, "touchstart").defaultPrevented).toBe(true);
  });

  it("leaves touches on gamepad buttons alone", () => {
    const { button } = mountStage();
    expect(dispatchTouch(button, "touchstart").defaultPrevented).toBe(false);
  });
});
