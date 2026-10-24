<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type {
  DeviceSchema,
  PS3ConsoleCreatePayload,
  PS3ProbeResponse,
} from "@/__generated__";
import { RAlert, RBtn, RDialog, RForm, RTextField } from "@/lib";
import deviceApi from "@/services/api/device";
import { errorMessage } from "@/utils/errorMessage";
import { integerBetween, notBlank } from "@/utils/validation";

const props = withDefaults(
  defineProps<{
    modelValue: boolean;
    /** The console to edit; null adds a new one. */
    device?: DeviceSchema | null;
    busy?: boolean;
  }>(),
  { device: null, busy: false },
);

const emit = defineEmits<{
  (e: "update:modelValue", value: boolean): void;
  (e: "submit", payload: PS3ConsoleCreatePayload): void;
}>();

const { t } = useI18n();

// What a new console starts with; the server applies the same when omitted.
const DEFAULTS = {
  ftp_port: 21,
  ps3_user: "00000001",
  poll_interval_minutes: 15,
  keep_versions: 10,
};

interface Draft {
  name: string;
  ip_address: string;
  ftp_port: string;
  ps3_user: string;
  poll_interval_minutes: string;
  keep_versions: string;
}

function draftOf(device: DeviceSchema | null): Draft {
  const config = { ...DEFAULTS, ...(device?.sync_config ?? {}) };
  return {
    name: device?.name ?? t("settings.ps3-default-name"),
    ip_address: device?.ip_address ?? "",
    ftp_port: String(config.ftp_port),
    ps3_user: String(config.ps3_user),
    poll_interval_minutes: String(config.poll_interval_minutes),
    keep_versions: String(config.keep_versions),
  };
}

const draft = ref<Draft>(draftOf(props.device));
const valid = ref(false);
const probing = ref(false);
const probe = ref<PS3ProbeResponse | null>(null);
const probeError = ref<string | null>(null);

const rules = {
  required: [notBlank()],
  port: [integerBetween(1, 65535)],
  user: [
    (v: string | number | null | undefined) =>
      /^\d{8}$/.test(String(v ?? "")) || t("settings.ps3-user-invalid"),
  ],
  interval: [integerBetween(1, 1440)],
  versions: [integerBetween(1, 100)],
};

const canSubmit = computed(() => valid.value && !props.busy);
const canProbe = computed(
  () => !!draft.value.ip_address.trim() && !probing.value,
);

const probeAlert = computed(() => {
  if (probeError.value) {
    return { type: "error" as const, text: probeError.value };
  }
  if (!probe.value) return null;
  if (!probe.value.reachable) {
    return {
      type: "warning" as const,
      text: t("settings.ps3-test-unreachable"),
    };
  }
  if (!probe.value.is_ftp) {
    return { type: "warning" as const, text: t("settings.ps3-test-no-ftp") };
  }
  return {
    type: "success" as const,
    text: t("settings.ps3-test-ok", {
      users: probe.value.users.join(", ") || "—",
    }),
  };
});

// Reopening resets the form, so a cancelled edit does not carry over.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    draft.value = draftOf(props.device);
    probe.value = null;
    probeError.value = null;
  },
  { immediate: true },
);

async function testConnection(): Promise<void> {
  if (!canProbe.value) return;
  probing.value = true;
  probe.value = null;
  probeError.value = null;
  try {
    const { data } = await deviceApi.probePS3({
      ip_address: draft.value.ip_address.trim(),
      ftp_port: Number(draft.value.ftp_port) || DEFAULTS.ftp_port,
    });
    probe.value = data;
    const [first] = data.users;
    if (first && !data.users.includes(draft.value.ps3_user)) {
      draft.value.ps3_user = first;
    }
  } catch (error) {
    probeError.value = errorMessage(error);
  } finally {
    probing.value = false;
  }
}

function close(): void {
  emit("update:modelValue", false);
}

function submit(): void {
  if (!canSubmit.value) return;
  const d = draft.value;
  emit("submit", {
    name: d.name.trim(),
    ip_address: d.ip_address.trim(),
    ftp_port: Number(d.ftp_port),
    ps3_user: d.ps3_user.trim(),
    poll_interval_minutes: Number(d.poll_interval_minutes),
    keep_versions: Number(d.keep_versions),
  });
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-sony-playstation"
    :width="520"
    cancelable
    :cancel-disabled="busy"
    @update:model-value="
      (v) => {
        if (!v) close();
      }
    "
  >
    <template #header>
      <span>{{ device ? t("settings.ps3-edit") : t("settings.ps3-add") }}</span>
    </template>

    <template #content>
      <RForm v-model="valid" class="r-ps3-dialog" @submit="submit">
        <RAlert
          type="info"
          variant="translucent"
          density="compact"
          :text="t('settings.ps3-dialog-intro')"
        />

        <RTextField
          v-model="draft.name"
          :label="t('common.name')"
          prefix-label="stacked"
          :rules="rules.required"
          :maxlength="255"
          required
        />

        <div class="r-ps3-dialog__row">
          <!-- eslint-disable vuejs-accessibility/no-autofocus -- the address is what a new console needs first -->
          <RTextField
            v-model="draft.ip_address"
            class="r-ps3-dialog__grow"
            :label="t('settings.ps3-ip-address')"
            prefix-label="stacked"
            placeholder="192.168.1.115"
            inputmode="decimal"
            :rules="rules.required"
            :autofocus="!device"
            required
          />
          <!-- eslint-enable vuejs-accessibility/no-autofocus -->
          <RTextField
            v-model="draft.ftp_port"
            class="r-ps3-dialog__narrow"
            type="number"
            min="1"
            max="65535"
            :label="t('settings.ps3-ftp-port')"
            prefix-label="stacked"
            :rules="rules.port"
            required
          />
        </div>

        <div class="r-ps3-dialog__probe">
          <RBtn
            variant="translucent"
            prepend-icon="mdi-lan-connect"
            :loading="probing"
            :disabled="!canProbe"
            @click="testConnection"
          >
            {{ t("settings.ps3-test") }}
          </RBtn>
          <RAlert
            v-if="probeAlert"
            class="r-ps3-dialog__grow"
            :type="probeAlert.type"
            variant="translucent"
            density="compact"
            :text="probeAlert.text"
            role="status"
          />
        </div>

        <RTextField
          v-model="draft.ps3_user"
          :label="t('settings.ps3-user')"
          :hint="t('settings.ps3-user-hint')"
          prefix-label="stacked"
          inputmode="numeric"
          :maxlength="8"
          :rules="rules.user"
          required
        />

        <div class="r-ps3-dialog__row">
          <RTextField
            v-model="draft.poll_interval_minutes"
            class="r-ps3-dialog__grow"
            type="number"
            min="1"
            max="1440"
            :label="t('settings.ps3-interval')"
            prefix-label="stacked"
            :rules="rules.interval"
            required
          />
          <RTextField
            v-model="draft.keep_versions"
            class="r-ps3-dialog__grow"
            type="number"
            min="1"
            max="100"
            :label="t('settings.ps3-keep-versions')"
            prefix-label="stacked"
            :rules="rules.versions"
            required
          />
        </div>
      </RForm>
    </template>

    <template #footer>
      <RBtn
        variant="flat"
        color="primary"
        prepend-icon="mdi-check"
        :loading="busy"
        :disabled="!canSubmit"
        @click="submit"
      >
        {{ t("common.save") }}
      </RBtn>
    </template>
  </RDialog>
</template>

<style scoped>
.r-ps3-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-ps3-dialog__row {
  display: flex;
  gap: var(--r-space-3);
  align-items: flex-start;
}

.r-ps3-dialog__grow {
  flex: 1 1 0;
  min-width: 0;
}

.r-ps3-dialog__narrow {
  flex: 0 0 112px;
}

.r-ps3-dialog__probe {
  display: flex;
  gap: var(--r-space-3);
  align-items: center;
  flex-wrap: wrap;
}
</style>

<style>
html[data-bp~="xs"] .r-ps3-dialog__row {
  flex-direction: column;
  align-items: stretch;
}

html[data-bp~="xs"] .r-ps3-dialog__narrow {
  flex-basis: auto;
}
</style>
