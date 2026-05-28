<script setup lang="ts">
// RForm — native `<form>` that provides a registration context so
// descendant form fields (RTextField, RSelect, RCheckbox) auto-enroll.
// The form aggregates their validity into `modelValue` and exposes
// `validate()` / `reset()` to consumers.
//
// Two QoL extras:
//   • Enter on any field submits when the form validates clean. Spares
//     the consumer from binding `@keyup.enter` on every input.
//   • After a failed `validate()`, scrolls the first invalid field
//     into view and focuses it.
import { computed, ref, useAttrs, watch } from "vue";
import type { RFormField } from "./context";
import { provideRForm } from "./context";

defineOptions({ inheritAttrs: false });

interface Props {
  /** v-model — true when every registered field passes its rules. */
  modelValue?: boolean;
  /** Disable the Enter-to-submit shortcut. */
  disableEnterSubmit?: boolean;
  /** Disable the scroll-to-first-error helper. */
  disableScrollToError?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: undefined,
  disableEnterSubmit: false,
  disableScrollToError: false,
});

const emit = defineEmits<{
  (e: "update:modelValue", v: boolean): void;
  (e: "submit", ev: Event): void;
}>();

const attrs = useAttrs();

const formRef = ref<HTMLFormElement | null>(null);

// ── Registry of descendant fields ───────────────────────────────
const fields = ref<RFormField[]>([]);

function register(field: RFormField) {
  if (!fields.value.includes(field)) fields.value.push(field);
}
function unregister(field: RFormField) {
  const i = fields.value.indexOf(field);
  if (i !== -1) fields.value.splice(i, 1);
}
provideRForm({ register, unregister });

// ── Public API ──────────────────────────────────────────────────
async function validate(): Promise<{ valid: boolean }> {
  const results = await Promise.all(fields.value.map((f) => f.validate()));
  const valid = results.every(Boolean);
  emit("update:modelValue", valid);
  if (!valid && !props.disableScrollToError) scrollToFirstError();
  return { valid };
}

function reset() {
  for (const f of fields.value) f.reset();
}
function resetValidation() {
  reset();
}

function scrollToFirstError() {
  const root = formRef.value;
  if (!root) return;
  // Prefer each field's own `el()` (more accurate than a DOM query),
  // fall back to a query for `[aria-invalid="true"]` so non-RForm-aware
  // fields are still handled.
  for (const f of fields.value) {
    const el = f.el?.();
    if (!el) continue;
    if (el.getAttribute("aria-invalid") === "true") {
      el.scrollIntoView({ block: "center", behavior: "smooth" });
      if (typeof el.focus === "function") el.focus();
      return;
    }
  }
  const target = root.querySelector<HTMLElement>('[aria-invalid="true"]');
  if (!target) return;
  target.scrollIntoView({ block: "center", behavior: "smooth" });
  if (typeof target.focus === "function") target.focus();
}

defineExpose({ validate, reset, resetValidation });

// Aggregate validity — flips reactively as any field gains or loses an
// error. Initial state is `true` (no errors yet); typing into a field
// with rules will make it `false` as soon as the first rule fails.
const allValid = computed(() => fields.value.every((f) => f.validity()));
watch(allValid, (v) => emit("update:modelValue", v), { immediate: true });

// ── Enter-to-submit ─────────────────────────────────────────────
async function onKeyDown(event: KeyboardEvent) {
  if (props.disableEnterSubmit) return;
  if (event.key !== "Enter") return;
  // Allow textarea newlines and explicit Shift+Enter combos.
  const tag = (event.target as HTMLElement | null)?.tagName ?? "";
  if (tag === "TEXTAREA" || event.shiftKey) return;
  event.preventDefault();
  const result = await validate();
  if (result.valid) emit("submit", event);
}

function onSubmit(ev: Event) {
  ev.preventDefault();
  emit("submit", ev);
}
</script>

<template>
  <!-- eslint-disable-next-line vuejs-accessibility/no-static-element-interactions -- form-level keydown implements Enter-to-submit (§VI.F); the form is the correct owner -->
  <form
    ref="formRef"
    v-bind="attrs"
    class="r-form"
    @submit="onSubmit"
    @keydown="onKeyDown"
  >
    <slot />
  </form>
</template>

<style scoped>
/* RForm renders a transparent native `<form>` — no chrome of its own.
   Consumers control layout via their own children. */
.r-form {
  display: contents;
}
</style>
