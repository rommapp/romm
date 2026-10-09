<script setup lang="ts">
import { RBtn, RDialog, RTextField } from "@v2/lib";
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type { ChannelSchema } from "@/__generated__";
import { typedMatches } from "@/v2/utils/typedConfirm";

defineOptions({ inheritAttrs: false });

const props = defineProps<{
  /** The channel to delete; null keeps the dialog closed. */
  channel: ChannelSchema | null;
  body: string;
  /** Deletes the channel. Resolves to close the dialog, rejects to keep it open. */
  onConfirm: () => Promise<void>;
}>();

const emit = defineEmits<{
  close: [];
}>();

const { t } = useI18n();

const typed = ref("");
const deleting = ref(false);

watch(
  () => props.channel?.id,
  () => {
    typed.value = "";
  },
);

const confirmDisabled = computed(
  () => !props.channel || !typedMatches(props.channel.label, typed.value),
);

function cancel() {
  if (!deleting.value) emit("close");
}

async function confirm() {
  if (confirmDisabled.value || deleting.value) return;
  deleting.value = true;
  await props.onConfirm().catch(() => undefined);
  deleting.value = false;
}
</script>

<template>
  <RDialog
    :model-value="channel !== null"
    icon="mdi-delete-outline"
    width="440"
    persistent
    v-bind="$attrs"
    @close="cancel"
  >
    <template v-if="channel" #header>
      <span>{{ t("channels.delete-title", { label: channel.label }) }}</span>
    </template>
    <template v-if="channel" #content>
      <div class="r-delete-channel">
        <p class="r-delete-channel__body">{{ body }}</p>
        <i18n-t
          keypath="common.type-to-confirm"
          tag="p"
          class="r-delete-channel__hint"
        >
          <template #label>
            <strong>{{ channel.label }}</strong>
          </template>
        </i18n-t>
        <RTextField
          v-model="typed"
          density="comfortable"
          variant="outlined"
          :disabled="deleting"
        />
      </div>
    </template>
    <template v-if="channel" #footer-start>
      <!-- eslint-disable vuejs-accessibility/no-autofocus -- RDialog reads [autofocus] to place initial focus, and Cancel is the safe default -->
      <RBtn autofocus variant="outlined" :disabled="deleting" @click="cancel">
        {{ t("common.cancel") }}
      </RBtn>
      <!-- eslint-enable vuejs-accessibility/no-autofocus -->
    </template>
    <template v-if="channel" #footer>
      <RBtn
        color="error"
        :loading="deleting"
        :disabled="confirmDisabled || deleting"
        @click="confirm"
      >
        {{ t("channels.delete") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-delete-channel {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-2);
}
.r-delete-channel__body {
  margin: 0 0 var(--r-space-2);
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
  line-height: var(--r-line-height-normal);
}
.r-delete-channel__hint {
  margin: 0;
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
}
.r-delete-channel__hint strong {
  color: var(--r-color-fg);
  font-family: var(--r-font-family-mono);
}
</style>
