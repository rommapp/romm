// Loaded only by tsconfig.v2.json; tsconfig.json excludes it, because
// `ComponentCustomProps` is global and v1 has components whose emits
// collide with the handlers declared here.
//
// `strictTemplates` (tsconfig.v2.json) drops the `Record<string, unknown>`
// that otherwise lets a component swallow any prop. That is the point: an
// undeclared prop is a bug. Native attributes are not, because a component
// forwarding `$attrs` to a DOM root legitimately accepts them, and nothing
// in the type system says which components do.
//
// Deliberately narrower than all of `HTMLAttributes`: `placeholder`,
// `color` and friends are plausible design-system props, so a typo in one
// should stay an error rather than pass as a global attribute. Native
// `id` is left out because components routinely declare it themselves
// with a numeric type, and most native event handlers are too:
// intersecting them with a component's own emits turns a same-named
// custom event (`toggle`, `submit`) into an uncallable handler. The three
// listed below are safe only while no v2 component emits them with a
// payload other than the native event.
import type {
  AnchorHTMLAttributes,
  AriaAttributes,
  ButtonHTMLAttributes,
  HTMLAttributes,
} from "vue";

type PointerAndKeyHandlers = Pick<
  HTMLAttributes,
  "onClick" | "onKeydown" | "onKeyup"
>;

// Not global, but meaningful on the element every one of these is
// forwarded to (a button, a link, a form control).
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
