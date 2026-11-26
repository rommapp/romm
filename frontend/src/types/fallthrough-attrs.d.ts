// `strictTemplates` drops the `Record<string, unknown>` that lets a component
// swallow any prop, so an undeclared prop is an error. Native attributes a
// component forwards to a DOM root are not, and the type system cannot say
// which components forward them.
//
// Deliberately narrower than `HTMLAttributes`: `placeholder`, `color` and
// friends are plausible design-system props, so a typo should stay an error.
// `id` is left out because components declare it with a numeric type, and
// most native handlers are too: intersecting them with a component's own
// emits makes a same-named custom event (`toggle`, `submit`) uncallable. The
// three below are safe while no component emits them with a non-native payload.
import type {
  AnchorHTMLAttributes,
  AriaAttributes,
  ButtonHTMLAttributes,
  HTMLAttributes,
} from "vue";

type PointerAndKeyHandlers = Pick<
  HTMLAttributes,
  | "onBlur"
  | "onClick"
  | "onKeydown"
  | "onKeyup"
  | "onLostpointercapture"
  | "onPointercancel"
  | "onPointerdown"
  | "onPointerup"
  | "onWheel"
>;

type ForwardedElementAttributes = Pick<
  ButtonHTMLAttributes,
  "autofocus" | "form"
> &
  Pick<AnchorHTMLAttributes, "rel">;

type GlobalAttributes = Pick<
  HTMLAttributes,
  | "contenteditable"
  | "dir"
  | "draggable"
  | "hidden"
  | "inert"
  | "lang"
  | "role"
  | "spellcheck"
  | "tabindex"
  | "title"
>;

declare module "vue" {
  interface ComponentCustomProps
    extends
      AriaAttributes,
      ForwardedElementAttributes,
      GlobalAttributes,
      PointerAndKeyHandlers {
    // Volar camelizes bound attributes on components, so `:data-focus-key`
    // arrives as `dataFocusKey` while a static `data-state` stays kebab.
    [dataAttribute: `data${string}`]: unknown;
  }

  interface HTMLAttributes {
    [dataAttribute: `data-${string}`]: unknown;
  }
}
