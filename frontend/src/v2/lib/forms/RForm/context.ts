// RForm context — the channel each form field uses to register itself
// with an ancestor `<RForm>` so the form can aggregate validity,
// validate the whole form on demand, and reset all children at once.
//
// Field components inject `useRFormRegistration()` and, if a form is
// present, register their `validate` + `reset` handles. The form keeps
// the registry, surfaces it via its public `validate()` / `reset()`
// methods, and computes `modelValue` (true when every field is valid).
import { inject, onBeforeUnmount, provide } from "vue";
import type { ComputedRef, InjectionKey } from "vue";

export interface RFormField {
  /** Run rules on the field; return true if no rule failed. */
  validate: () => boolean | Promise<boolean>;
  /** Clear dirty state + cached errors (does not touch the model). */
  reset: () => void;
  /** Used by `scrollToFirstError` — the DOM element to focus + scroll. */
  el?: () => HTMLElement | null;
  /** Reactive validity — `false` while the field shows an error, `true`
   *  otherwise. The form aggregates these to drive its own `modelValue`. */
  validity: ComputedRef<boolean>;
}

export interface RFormApi {
  register: (field: RFormField) => void;
  unregister: (field: RFormField) => void;
}

export const RFormKey: InjectionKey<RFormApi> = Symbol("RForm");

/** Use inside a form field. Auto-unregisters on unmount. */
export function useRFormRegistration(field: RFormField) {
  const api = inject(RFormKey, null);
  if (!api) return;
  api.register(field);
  onBeforeUnmount(() => api.unregister(field));
}

export function provideRForm(api: RFormApi) {
  provide(RFormKey, api);
}
