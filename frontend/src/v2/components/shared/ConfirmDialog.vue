<script setup lang="ts">
// ConfirmDialog — single mounted shared composite that renders confirmation
// prompts on demand. Consumers don't render this directly; they go through
// `useConfirm()` (src/v2/composables/useConfirm), which emits the
// `showConfirm` event and resolves a Promise<boolean> when the user picks.
//
// Three friction levels:
//   * Low:    title + body + Cancel + Confirm. Default focus on Cancel so
//             a stray Enter cancels.
//   * High:   `requireTyped` populated — the confirm button stays disabled
//             until the user types the matching string. Use for actions
//             that touch filesystem (per the constitution).
// Tone defaults to "warning"; pass "danger" for irreversible-and-serious.
import { RBtn, RDialog, RTextField } from "@v2/lib";
import type { Emitter } from "mitt";
import {
  computed,
  inject,
  nextTick,
  onBeforeUnmount,
  onMounted,
  ref,
} from "vue";
import { useI18n } from "vue-i18n";
import type { Events } from "@/types/emitter";

defineOptions({ inheritAttrs: false });

const { t } = useI18n();

type Payload = Events["showConfirm"];

const emitter = inject<Emitter<Events>>("emitter");
const open = ref(false);
const payload = ref<Payload | null>(null);
const typed = ref("");
const cancelButtonRef = ref<InstanceType<typeof RBtn> | null>(null);

const tone = computed(() => payload.value?.tone ?? "warning");
const confirmColor = computed(() =>
  tone.value === "danger" ? "error" : "warning",
);
const confirmDisabled = computed(() => {
  const required = payload.value?.requireTyped;
  if (!required) return false;
  return typed.value.trim() !== required;
});

function onShow(p: Payload) {
  payload.value = p;
  typed.value = "";
  open.value = true;
  nextTick(() => {
    cancelButtonRef.value?.$el?.focus?.();
  });
}

function resolve(confirmed: boolean) {
  const id = payload.value?.id;
  open.value = false;
  if (id != null) emitter?.emit("confirmResolved", { id, confirmed });
  payload.value = null;
  typed.value = "";
}

function onCancel() {
  resolve(false);
}

function onConfirm() {
  if (confirmDisabled.value) return;
  resolve(true);
}

onMounted(() => emitter?.on("showConfirm", onShow));
onBeforeUnmount(() => emitter?.off("showConfirm", onShow));
</script>

<template>
  <RDialog v-model="open" width="440" persistent>
    <template v-if="payload" #header>
      <span>{{ payload.title }}</span>
    </template>
    <template v-if="payload" #content>
      <div class="r-confirm">
        <p v-if="payload.body" class="r-confirm__body">{{ payload.body }}</p>

        <div v-if="payload.requireTyped" class="r-confirm__typed">
          <i18n-t
            keypath="common.type-to-confirm"
            tag="p"
            class="r-confirm__typed-hint"
          >
            <template #label>
              <strong>{{ payload.requireTyped }}</strong>
            </template>
          </i18n-t>
          <RTextField
            v-model="typed"
            density="comfortable"
            variant="outlined"
          />
        </div>
      </div>
    </template>
    <template v-if="payload" #footer>
      <div class="r-confirm__actions">
        <RBtn ref="cancelButtonRef" variant="text" @click="onCancel">
          {{ payload.cancelText ?? t("common.cancel") }}
        </RBtn>
        <RBtn
          :color="confirmColor"
          :disabled="confirmDisabled"
          @click="onConfirm"
        >
          {{ payload.confirmText ?? t("common.confirm") }}
        </RBtn>
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
.r-confirm {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-4);
}

.r-confirm__body {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
  line-height: var(--r-line-height-normal);
}

.r-confirm__typed {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}

.r-confirm__typed-hint {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}

.r-confirm__typed-hint strong {
  color: var(--r-color-fg);
  font-family: var(--r-font-family-mono);
}

.r-confirm__actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--r-space-2);
  width: 100%;
}
</style>
