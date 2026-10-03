import { useElementSize } from "@vueuse/core";
import { onScopeDispose, type Ref } from "vue";

/** A CSS length resolved to px, for values JS can't parse, such as `var()` or
 *  `env()`. Stays current as the value changes (a safe-area inset on rotation).
 *
 *  Args:
 *    expr: Any CSS length, e.g. `var(--r-nav-h)`.
 */
export function useCssLength(expr: string): Readonly<Ref<number>> {
  const probe = document.createElement("div");
  probe.setAttribute("aria-hidden", "true");
  probe.style.cssText =
    "position: fixed; top: 0; left: 0; width: 0; visibility: hidden; pointer-events: none";
  probe.style.height = expr;
  document.body.appendChild(probe);
  onScopeDispose(() => probe.remove());
  return useElementSize(probe, undefined, { box: "border-box" }).height;
}
