/**
 * Manager-side half of the gamepad POC (preview.ts + .storybook/gamepad/ is the other half).
 *
 * Storybook has no supported API for emoji-only toolbar labels, so this addon:
 * - Listens for GAMEPAD_TOOLBAR_LABEL_EVENT from the preview (GamepadStoryHost).
 * - Recomputes the label on GLOBALS_UPDATED via toolbarSync.resolveToolbarLabelOnGlobalsUpdate.
 * - DOM-patches the gamepadInput toolbar button (hide SVG, set span text, accent when On).
 *
 * Preview and manager share logic in gamepad/toolbarSync.ts to avoid caption/global drift.
 */
import { GLOBALS_UPDATED } from "storybook/internal/core-events";
import { addons } from "storybook/manager-api";
import { GAMEPAD_TOOLBAR_LABEL_EVENT } from "./gamepad/constants";
import {
  fallbackGamepadToolbarLabel,
  resolveToolbarLabelOnGlobalsUpdate,
  shouldApplyPreviewToolbarLabel,
} from "./gamepad/toolbarSync";

let lastLabel = fallbackGamepadToolbarLabel(false);

function ensureToolbarStyles() {
  if (document.getElementById("romm-gpad-toolbar-style")) return;
  const style = document.createElement("style");
  style.id = "romm-gpad-toolbar-style";
  style.textContent = `
    button[data-romm-gamepad-control="true"] svg {
      display: none !important;
    }
    button[data-romm-gamepad-on="true"] {
      color: var(--sb-color-accent, #029cfd);
      font-weight: 600;
    }
  `;
  document.head.appendChild(style);
}

function findGamepadToolbarButton(): HTMLButtonElement | null {
  for (const btn of document.querySelectorAll<HTMLButtonElement>("button")) {
    if (btn.id.includes("gamepadInput")) return btn;
    const aria = btn.getAttribute("aria-label") ?? "";
    const text = (btn.textContent ?? "").trim();
    if (aria.includes("Gamepad") || text.includes("Gamepad")) {
      return btn;
    }
  }
  return null;
}

function writeButtonLabel(btn: HTMLButtonElement, label: string) {
  for (const svg of btn.querySelectorAll("svg")) {
    svg.style.display = "none";
  }

  const spans = [...btn.querySelectorAll("span")].filter(
    (span) => !span.querySelector("svg"),
  );
  if (spans.length > 0) {
    spans[0].textContent = label;
    return;
  }

  btn.textContent = label;
}

function applyToolbarLabel(label: string) {
  if (!label.trim()) return false;
  ensureToolbarStyles();
  lastLabel = label;
  const btn = findGamepadToolbarButton();
  if (!btn) return false;

  btn.dataset.rommGamepadControl = "true";
  btn.setAttribute("aria-label", label);
  btn.setAttribute("title", label);

  const on = label.includes("Gamepad: On");
  btn.dataset.rommGamepadOn = on ? "true" : "false";

  writeButtonLabel(btn, label);
  return true;
}

function scheduleApply(label: string) {
  requestAnimationFrame(() => applyToolbarLabel(label));
}

addons.register("romm/storybook-gamepad-toolbar-sync", (api) => {
  const channel = addons.getChannel();

  channel.on(GAMEPAD_TOOLBAR_LABEL_EVENT, (label: string) => {
    if (typeof label !== "string" || !label.trim()) return;
    if (!shouldApplyPreviewToolbarLabel(api.getGlobals(), label)) return;
    scheduleApply(label);
  });

  channel.on(GLOBALS_UPDATED, ({ globals }) => {
    scheduleApply(resolveToolbarLabelOnGlobalsUpdate(globals));
  });
});
