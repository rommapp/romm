<script setup lang="ts">
// RMenu — the only floating-menu primitive: owns the
// glass panel surface, the activator wiring, optional search header,
// click-outside / Escape / close-on-content-click, and the open
// transition. Built on `@floating-ui/vue` for positioning, sharing the
// same vocabulary as RTooltip and RSelect.
//
// Activator pattern:
//
//   <RMenu>
//     <template #activator="{ props }">
//       <RBtn v-bind="props">Open</RBtn>
//     </template>
//     <RMenuItem>Item</RMenuItem>
//     <RDivider />
//     <RMenuItem>Another</RMenuItem>
//   </RMenu>
//
// `searchable` adds a sticky `RTextField` at the top of the panel and
// surfaces `v-model:search` for the query — same pattern as RSelect's
// inline search.
//
// The previous wrapper trio (RMenuPanel / RMenuHeader / RMenuDivider /
// RMenuSearch) is gone; their roles collapse into RMenu (panel, search)
// or into call-site markup + RDivider (headers, dividers).
import {
  autoUpdate,
  flip,
  offset as offsetMiddleware,
  shift,
  size as sizeMiddleware,
  useFloating,
} from "@floating-ui/vue";
import type { Placement } from "@floating-ui/vue";
import {
  computed,
  nextTick,
  onBeforeUnmount,
  onMounted,
  provide,
  ref,
  useAttrs,
  useSlots,
  watch,
} from "vue";
import { useInputModality } from "@/v2/composables/useInputModality";
import { opensInNewContext } from "@/v2/utils/mouseGestures";
import RTextField from "../../forms/RTextField/RTextField.vue";
import {
  type EscapableEntry,
  popEscapable,
  pushEscapable,
} from "../../overlays/RDialog/escapeStack.js";
import RIcon from "../../primitives/RIcon/RIcon.vue";
import { RMenuCloseKey } from "./context";

defineOptions({ inheritAttrs: false });

type Anchor =
  | "top"
  | "bottom"
  | "start"
  | "end"
  | "top start"
  | "top end"
  | "bottom start"
  | "bottom end"
  | "start top"
  | "start bottom"
  | "end top"
  | "end bottom";

interface Props {
  /** Open state (controlled). Use v-model. Omit for uncontrolled. */
  modelValue?: boolean;
  /** Close when the user clicks inside the panel (default: true). */
  closeOnContentClick?: boolean;
  /** Open on hover instead of click (e.g. dropdown menus on a nav). */
  openOnHover?: boolean;
  /** Anchor — mapped to a floating-ui placement. */
  location?: Anchor;
  /** Px gap between activator and panel. */
  offset?: number;
  /** Override the panel width (default: auto, with a 180 px floor). */
  width?: string | number;
  /** Cap the panel height — body scrolls beyond it. */
  maxHeight?: string | number;
  /** Render a sticky search input at the top. */
  searchable?: boolean;
  /** v-model:search — current query string. */
  search?: string;
  searchPlaceholder?: string;
  searchAutoFocus?: boolean;
  /** Extra class merged onto the panel element. */
  contentClass?: string;
  /** Disable opening entirely. */
  disabled?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: undefined,
  closeOnContentClick: true,
  openOnHover: false,
  location: "bottom",
  offset: 8,
  width: undefined,
  maxHeight: undefined,
  searchable: false,
  search: "",
  searchPlaceholder: "",
  searchAutoFocus: true,
  contentClass: undefined,
  disabled: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "update:search", v: string): void;
  (e: "open"): void;
  (e: "close"): void;
}>();

const slots = useSlots();
const attrs = useAttrs();

// ── Open state ──────────────────────────────────────────────────
// Same controlled/uncontrolled idiom RDialog / RTooltip / RSelect use.
const internalOpen = ref(false);
const isOpen = computed(() =>
  props.modelValue !== undefined ? !!props.modelValue : internalOpen.value,
);
function setOpen(v: boolean) {
  if (props.modelValue !== undefined) {
    emit("update:modelValue", v);
  } else {
    internalOpen.value = v;
  }
  if (v) emit("open");
  else emit("close");
}

function open() {
  if (props.disabled) return;
  if (isOpen.value) return;
  setOpen(true);
}
function close() {
  if (!isOpen.value) return;
  setOpen(false);
}
function toggle() {
  if (isOpen.value) close();
  else open();
}

provide(RMenuCloseKey, close);

// ── Refs ────────────────────────────────────────────────────────
// The activator slot renders inside a `display: contents` span; we
// read its first child as the floating-ui reference (the actual
// activator element the user passed in).
const activatorWrapper = ref<HTMLElement | null>(null);
const reference = ref<Element | null>(null);
const panelRef = ref<HTMLElement | null>(null);

// ── Placement translation ───────────────────────────────────────
const PLACEMENT_MAP: Record<Anchor, Placement> = {
  top: "top",
  bottom: "bottom",
  start: "left",
  end: "right",
  "top start": "top-start",
  "top end": "top-end",
  "bottom start": "bottom-start",
  "bottom end": "bottom-end",
  "start top": "left-start",
  "start bottom": "left-end",
  "end top": "right-start",
  "end bottom": "right-end",
};
const placement = computed<Placement>(
  () => PLACEMENT_MAP[props.location] ?? "bottom-start",
);

// ── Sizing ──────────────────────────────────────────────────────
const widthCss = computed(() => {
  if (props.width === undefined) return undefined;
  return typeof props.width === "number" ? `${props.width}px` : props.width;
});
const maxHeightCss = computed(() => {
  if (props.maxHeight === undefined) return undefined;
  return typeof props.maxHeight === "number"
    ? `${props.maxHeight}px`
    : props.maxHeight;
});

const { floatingStyles } = useFloating(reference, panelRef, {
  placement,
  strategy: "fixed",
  open: isOpen,
  transform: false,
  whileElementsMounted: autoUpdate,
  middleware: computed(() => [
    offsetMiddleware(props.offset),
    flip({ padding: 8 }),
    shift({ padding: 8 }),
    sizeMiddleware({
      apply({ availableHeight, elements }) {
        const cap = maxHeightCss.value ?? `${availableHeight}px`;
        Object.assign(elements.floating.style, { maxHeight: cap });
      },
      padding: 8,
    }),
  ]),
});

// ── Hover bridge ────────────────────────────────────────────────
// When `openOnHover` is true the menu must also auto-close on
// mouseleave. The bridge between activator and panel is the tricky
// part: a naive mouseleave-on-activator would fire as soon as the
// pointer moves toward the panel, killing the menu mid-traversal.
// Solution: schedule the close on mouseleave with a short delay; any
// mouseenter on activator OR panel cancels the pending close.
const HOVER_CLOSE_DELAY = 140;
let hoverCloseTimer: ReturnType<typeof setTimeout> | null = null;

function cancelHoverClose() {
  if (hoverCloseTimer != null) {
    clearTimeout(hoverCloseTimer);
    hoverCloseTimer = null;
  }
}

function scheduleHoverClose() {
  cancelHoverClose();
  hoverCloseTimer = setTimeout(() => {
    hoverCloseTimer = null;
    close();
  }, HOVER_CLOSE_DELAY);
}

onBeforeUnmount(() => cancelHoverClose());

// ── Activator props ─────────────────────────────────────────────
// Spread these onto whatever element the consumer renders. We bind
// hover-open lazily so single-listener pattern doesn't break when the
// caller swaps activator at runtime.
const activatorProps = computed(() => {
  const out: Record<string, unknown> = {
    onClick: (evt: MouseEvent) => {
      if (props.disabled) return;
      // Don't follow links / submit forms when the activator opens a menu.
      evt.preventDefault();
      toggle();
    },
    "aria-haspopup": "menu",
    "aria-expanded": isOpen.value,
  };
  if (props.openOnHover) {
    out.onMouseenter = () => {
      cancelHoverClose();
      open();
    };
    out.onMouseleave = () => scheduleHoverClose();
  }
  return out;
});

// ── Click-outside ──────────────────────────────────────────────
function onDocPointerDown(evt: PointerEvent) {
  if (!isOpen.value) return;
  const target = evt.target as Node | null;
  if (!target) return;
  if (
    reference.value &&
    (reference.value as HTMLElement).contains(target as HTMLElement)
  )
    return;
  if (panelRef.value?.contains(target)) return;
  close();
}

// ── Escape / B-button dismissal ────────────────────────────────
// Register on the shared overlay-escape stack so a single global
// listener handles Esc across menus, dialogs, drawers — and so
// `useGamepad`'s B-back action can close the topmost overlay without
// reaching into the DOM. LIFO ordering means nested menus close one
// at a time (the inner-most first), matching the previous per-instance
// `document.keydown` behaviour.
const escEntry: EscapableEntry = {
  close: () => close(),
  persistent: false,
};

watch(
  () => isOpen.value,
  (open) => {
    if (open) pushEscapable(escEntry);
    else popEscapable(escEntry);
  },
);

onMounted(() => {
  reference.value = activatorWrapper.value?.firstElementChild ?? null;
  document.addEventListener("pointerdown", onDocPointerDown, true);
});
onBeforeUnmount(() => {
  document.removeEventListener("pointerdown", onDocPointerDown, true);
  // Safety: if we unmount while open (route change while the menu is
  // visible) drop our entry so the stack doesn't dereference a dead
  // close function.
  popEscapable(escEntry);
});

// Re-read the reference if the slot content changes (e.g., v-if flips).
watch(
  () => slots.activator,
  () => {
    reference.value = activatorWrapper.value?.firstElementChild ?? null;
  },
);

// ── Close-on-content-click ─────────────────────────────────────
// Fires after the inner element's @click — Vue's natural bubbling
// order. Elements marked `data-r-menu-no-close` (e.g. the search
// header, custom keep-open regions) opt out.
function onPanelClick(evt: MouseEvent) {
  if (!props.closeOnContentClick) return;
  const target = evt.target as HTMLElement | null;
  if (!target) return;
  if (target.closest("[data-r-menu-no-close]")) return;
  // A modifier-click on a link is a browser "open in new tab/window"
  // gesture (see opensInNewContext). Closing the menu would unmount the
  // teleported <a> before the browser performs its default action,
  // swallowing the new tab — so leave the menu open and let it through.
  if (opensInNewContext(evt) && target.closest("a[href]")) return;
  close();
}

const mergedContentClass = computed(() =>
  ["r-menu__panel", props.contentClass].filter(Boolean).join(" "),
);

// ── Keyboard / gamepad in-panel navigation ─────────────────────
// Items are <button> / <router-link> rendered via RMenuItem — they're
// natively focusable, but the panel itself doesn't react to ArrowUp /
// ArrowDown. Add a panel-level handler so D-pad / left-stick (mapped to
// arrows by `useGamepad`) cycle through the items.
function focusableMenuItems(): HTMLElement[] {
  const panel = panelRef.value;
  if (!panel) return [];
  return Array.from(panel.querySelectorAll<HTMLElement>(".r-menu-item")).filter(
    (el) =>
      !el.hasAttribute("disabled") &&
      !el.classList.contains("r-menu-item--disabled") &&
      el.offsetParent !== null,
  );
}

function onPanelKeydown(evt: KeyboardEvent) {
  if (evt.key !== "ArrowUp" && evt.key !== "ArrowDown") return;
  const items = focusableMenuItems();
  if (items.length === 0) return;
  const activeIdx = items.findIndex((el) => el === document.activeElement);
  let nextIdx: number;
  if (evt.key === "ArrowDown") {
    nextIdx = activeIdx === -1 ? 0 : (activeIdx + 1) % items.length;
  } else {
    nextIdx =
      activeIdx === -1
        ? items.length - 1
        : (activeIdx - 1 + items.length) % items.length;
  }
  evt.preventDefault();
  items[nextIdx]?.focus();
}

// Autofocus the first menu item when the panel opens via keyboard or
// gamepad — mouse users keep the legacy "menu opens, pointer drives"
// behaviour so an opened-by-hover menu doesn't yank focus away from
// whatever the user was about to click. Skipped when `searchable` is
// true (the search input owns initial focus).
const { modality } = useInputModality();

watch(
  () => isOpen.value,
  async (open) => {
    if (!open) return;
    if (props.searchable) return;
    if (modality.value !== "pad" && modality.value !== "key") return;
    await nextTick();
    // One more frame so the panel mount + floating-ui's positioning
    // commit before we try to focus — without it the first item is
    // measured at (0, 0) and a follow-up `scrollIntoView` would jump
    // the page.
    await new Promise<void>((resolve) =>
      requestAnimationFrame(() => resolve()),
    );
    const items = focusableMenuItems();
    items[0]?.focus();
  },
);
</script>

<template>
  <span ref="activatorWrapper" class="r-menu" style="display: contents">
    <slot
      name="activator"
      :props="activatorProps"
      :is-open="isOpen"
      :open="open"
      :close="close"
      :toggle="toggle"
    />
  </span>

  <Teleport to="body">
    <Transition name="r-menu-pop">
      <!-- eslint-disable vuejs-accessibility/mouse-events-have-key-events --
           hover-bridge mouseenter/mouseleave have no keyboard equivalent —
           keyboard users navigate the panel via arrow keys + Escape, which
           are already wired up. focusin/focusout don't apply at the panel
           level since menu items own focus, not the panel container. -->
      <!-- eslint-disable-next-line vuejs-accessibility/interactive-supports-focus -- panel routes keydown for its items; focus lives on the menu items, not this container -->
      <div
        v-if="isOpen"
        ref="panelRef"
        v-bind="attrs"
        :class="mergedContentClass"
        :style="{ ...floatingStyles, width: widthCss, maxHeight: maxHeightCss }"
        role="menu"
        @click="onPanelClick"
        @keydown="onPanelKeydown"
        @mouseenter="openOnHover && cancelHoverClose()"
        @mouseleave="openOnHover && scheduleHoverClose()"
      >
        <!-- Sticky search header. `data-r-menu-no-close` keeps clicks
             on the input from triggering the panel-level close. -->
        <div
          v-if="searchable"
          class="r-menu__search"
          data-r-menu-no-close
          @mousedown.stop
        >
          <!-- eslint-disable vuejs-accessibility/no-autofocus -- autofocusing the search field on menu open is intentional modal UX -->
          <RTextField
            :model-value="search"
            :placeholder="searchPlaceholder"
            prefix-label="inline"
            hide-details
            density="compact"
            autocomplete="off"
            :autofocus="searchAutoFocus"
            @update:model-value="(v) => emit('update:search', String(v ?? ''))"
          >
            <template #prefix-label>
              <RIcon icon="mdi-magnify" size="16" />
            </template>
          </RTextField>
          <!-- eslint-enable vuejs-accessibility/no-autofocus -->
        </div>

        <div class="r-menu__body">
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.r-menu__panel {
  position: fixed;
  z-index: var(--r-z-menu, 2500);
  display: flex;
  flex-direction: column;
  /* No hard max-width — the panel grows to fit the widest item so a
     horizontal scrollbar never appears. Consumer can pass `width` for a
     fixed shell (e.g. UserMenu's 260px). */
  min-width: 180px;
  width: max-content;
  /* Never exceed the viewport — on a narrow phone a wide menu would
     otherwise overflow the screen edge (floating-ui's `shift` keeps it
     in view but can't shrink it). Caps both auto-width and fixed-`width`
     panels; the body already scrolls vertically and clips horizontally. */
  max-width: calc(100vw - 16px);
  overflow: hidden;
  background: var(--r-color-panel);
  border: 1px solid var(--r-color-panel-border);
  border-radius: 10px;
  box-shadow:
    0 20px 60px color-mix(in srgb, black 70%, transparent),
    0 4px 20px color-mix(in srgb, black 40%, transparent);
  backdrop-filter: blur(28px);
  -webkit-backdrop-filter: blur(28px);
  color: var(--r-color-fg);
  font-family: var(--r-font-family-sans);
}

.r-menu__search {
  flex-shrink: 0;
  padding: 6px;
  border-bottom: 1px solid var(--r-color-border);
}

.r-menu__body {
  flex: 1 1 auto;
  min-height: 0;
  display: flex;
  flex-direction: column;
  padding: 6px;
  /* Explicit both axes — `overflow-y: auto` alone makes `overflow-x`
     compute to `auto` (CSS spec), which would paint a horizontal
     scrollbar when content nudges the layout by even a subpixel. */
  overflow-x: hidden;
  overflow-y: auto;
  scrollbar-width: thin;
  scrollbar-color: var(--r-color-border-strong) transparent;
}
.r-menu__body::-webkit-scrollbar {
  width: 8px;
}
.r-menu__body::-webkit-scrollbar-thumb {
  background: var(--r-color-border-strong);
  border-radius: 4px;
}
.r-menu__body::-webkit-scrollbar-thumb:hover {
  background: var(--r-color-fg-faint);
}

/* When searchable, the header has its own border; drop the body's
   top padding so items butt up to the divider instead of sitting in
   a wide empty band. */
.r-menu__panel:has(.r-menu__search) .r-menu__body {
  padding-top: 0;
}

/* Menu-friendly spacing for any RDivider the consumer drops in. Saves
   every call-site from adding `class="my-2"` manually. */
.r-menu__body :deep(.r-divider:not(.r-divider--vertical)) {
  margin: 6px 2px;
}

/* ── Open / close motion ────────────────────────────────────── */
.r-menu-pop-enter-from {
  opacity: 0;
  transform: translateY(-4px) scale(0.98);
}
.r-menu-pop-enter-active {
  transition:
    opacity 140ms var(--r-motion-ease-out),
    transform 220ms cubic-bezier(0.34, 1.56, 0.64, 1);
  transform-origin: top center;
}
/* Close is instant — same idiom as RDialog. Removing the leave-active
   transition means Vue unmounts on the same frame. */

@media (prefers-reduced-motion: reduce) {
  .r-menu-pop-enter-from {
    transform: none;
  }
  .r-menu-pop-enter-active {
    transition: opacity 100ms linear;
  }
}
</style>
