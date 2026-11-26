// Native attributes a component may forward to a DOM root. `id` and most
// handlers are left out: they collide with numeric `id` props and same-named emits.
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
