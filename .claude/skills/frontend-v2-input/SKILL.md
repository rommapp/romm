---
name: frontend-v2-input
description: Universal input (mouse, touch, keyboard, gamepad) and responsive/universal-viewport layout in the RomM v2 frontend. Use when adding interactive v2 components, focus management, spatial navigation, gamepad/keyboard handling, modality-gated focus rings, breakpoints, or responsive layout. Covers useInput, focus geometry primitives, the overlay scope stack, useBreakpoint, and the data-bp/data-input attributes. Trigger on interactive or responsive work under frontend/src/v2/.
---

# RomM v2 — Universal Input & Universal Viewport

**Premise:** all v2 UI works with mouse, touch, keyboard, **and** gamepad; and every surface reads cleanly from a 320px phone to a 4K display. Both mechanisms are fixed — don't invent a parallel one.

The input system lives in `src/v2/composables/useInput/` (bus, keyboard, gamepad, actions, scope). It generalises the original gamepad-only `src/console/` system. There are **no `/console/*` routes in v2**.

---

## Modality

`useInputModality` sets `data-input="mouse|touch|key|pad"` on `<html>` from the most recent input.

- **Focus rings appear only with `key` and `pad`** (CSS in `global.css`). **Never use bare `:focus` in styles** — use the modality-gated selectors, or focus rings flash on mouse click.
- Hit targets may scale up for `touch` and `pad`.

## Coverage — every interactive primitive participates

Buttons, list items, tabs, menu items, focusable cards, toggleable chips — all participate in spatial navigation (not optional). A new interactive primitive must:

- be focusable (proper `tabindex`, or already so via a wrapped Vuetify component);
- react to logical actions (confirm/cancel) from `useInput`, in addition to native click;
- show a modality-gated focus state.

Storybook `play()` covering gamepad input is required **only when applicable** (the primitive is interactive enough that gamepad navigation matters).

## Focus geometry

Each view declares its layout with focus primitives: `RFocusZone`, `RFocusGrid`, `RFocusRow`, `RFocusColumn`. Multiple regions = multiple zones. Predictable up/down/left/right movement is the view's responsibility.

## Element-level global shortcuts

Above per-view geometry, some elements bind globally regardless of focus location:

- `UserMenu` opens on **Start**.
- Navbar tabs cycle with **LB/RB** (plus D-pad).
- Context menu opens on **X or Y**.

## Scope (overlay stack)

When a dialog opens, push a scope; when it closes, pop. This stops Escape from closing two things at once and stops `confirm` leaking to controls beneath an overlay. `RDialog` and `RMenu` manage their scope automatically — custom overlays are an anti-pattern; go through the primitives.

---

## Responsive layout (universal viewport)

- **Single breakpoint source: `useBreakpoint`** (`src/v2/composables/useBreakpoint/`). Material thresholds — `xs <600`, `sm 600–959`, `md 960–1279`, `lg 1280–1919`, `xl ≥1920`. `installBreakpointAttribute()` (mounted once in `AppLayout`) mirrors the active set onto `<html data-bp="…">`.
- **Layout switches live in CSS** via the attribute selector: `html[data-bp~="xs"] .foo { … }`, `html[data-bp~="sm-and-down"] .foo { … }`. **No raw `@media` for layout** — the only allowed `@media` are `prefers-reduced-motion` and print. The attribute is on `<html>` so it reaches teleported overlays.
- **Conditional rendering** (mount/unmount a different component per tier) uses the `useBreakpoint()` refs in `<script>` — e.g. `v-if="xs"`. Prefer mount-gating over `display:none` for focusable chrome so hidden controls never sit in the tab/spatial-nav order.
- **`--r-row-pad` is the global horizontal gutter**, already re-scoped responsive in `global.css` (36 → 20 → 14px). Consume `var(--r-row-pad)`; don't hard-code a smaller `xs` padding per component.
- **Touch targets** ≥ `--r-touch-target` (44px) on `xs`/touch. Gate the bump to touch/pad where desktop sizing would bloat.
- **Overlays go full-bleed on `xs`.** `RDialog` renders full-screen / bottom-sheet on phones (`fullscreenOnMobile`, default on); `RMenu` bottom-sheets large menus. Never float a 600px dialog on a 360px screen.
- **Label→icon collapse** (the AppNav precedent) is the canonical way to compress chrome; the four primary destinations relocate to `BottomNav` on `sm-and-down`.
- **Grids** size via `useResponsiveColumns` (ResizeObserver), never a fixed column count.

Verification adds a breakpoint sweep — see `pre-pr-verification`.
