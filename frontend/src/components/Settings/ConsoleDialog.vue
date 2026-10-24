<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import type {
  ConsoleCreatePayload,
  ConsoleProbeResponse,
  ConsoleUserSchema,
  DeviceSchema,
} from "@/__generated__";
import { RAlert, RBtn, RDialog, RForm, RSelect, RTextField } from "@/lib";
import deviceApi from "@/services/api/device";
import { errorMessage } from "@/utils/errorMessage";
import { integerBetween, notBlank, required } from "@/utils/validation";

type ConsoleKind = ConsoleCreatePayload["console"];

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
  (e: "submit", payload: ConsoleCreatePayload): void;
}>();

const { t } = useI18n();

const consoles = computed<{ title: string; value: ConsoleKind }[]>(() => [
  { title: t("settings.console-ps3"), value: "ps3" },
]);

// What a new console starts with; the server applies the same when omitted.
const DEFAULTS = {
  ftp_port: 21,
  poll_interval_minutes: 15,
  keep_versions: 10,
};

interface Draft {
  console: ConsoleKind;
  name: string;
  ip_address: string;
  ftp_port: string;
  ps3_user: string | null;
  poll_interval_minutes: string;
  keep_versions: string;
}

function draftOf(device: DeviceSchema | null): Draft {
  const config = { ...DEFAULTS, ...(device?.sync_config ?? {}) };
  return {
    console: "ps3",
    name: device?.name ?? t("settings.console-ps3"),
    ip_address: device?.ip_address ?? "",
    ftp_port: String(config.ftp_port),
    ps3_user:
      typeof device?.sync_config?.ps3_user === "string"
        ? device.sync_config.ps3_user
        : null,
    poll_interval_minutes: String(config.poll_interval_minutes),
    keep_versions: String(config.keep_versions),
  };
}

const draft = ref<Draft>(draftOf(props.device));
const valid = ref(false);
const probing = ref(false);
const probe = ref<ConsoleProbeResponse | null>(null);
const probeError = ref<string | null>(null);

const rules = {
  required: [notBlank()],
  user: [required()],
  port: [integerBetween(1, 65535)],
  interval: [integerBetween(1, 1440)],
  versions: [integerBetween(1, 100)],
};

function userTitle(user: ConsoleUserSchema): string {
  return user.name ? `${user.id} · ${user.name}` : user.id;
}

// Until a test lists the profiles, an edited console still shows its own.
const users = computed(() => {
  const listed = probe.value?.is_ftp ? probe.value.users : [];
  const current = draft.value.ps3_user;
  const known =
    current && !listed.some((u) => u.id === current)
      ? [{ id: current, name: null }, ...listed]
      : listed;
  return known.map((user) => ({ title: userTitle(user), value: user.id }));
});

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
      text: t("settings.console-test-unreachable"),
    };
  }
  if (!probe.value.is_ftp) {
    return {
      type: "warning" as const,
      text: t("settings.console-test-no-ftp"),
    };
  }
  if (!probe.value.users.length) {
    return {
      type: "warning" as const,
      text: t("settings.console-test-no-users"),
    };
  }
  return { type: "success" as const, text: t("settings.console-test-ok") };
});

async function testConnection(): Promise<void> {
  if (!canProbe.value) return;
  probing.value = true;
  probe.value = null;
  probeError.value = null;
  try {
    const { data } = await deviceApi.probeConsole({
      console: draft.value.console,
      ip_address: draft.value.ip_address.trim(),
      ftp_port: Number(draft.value.ftp_port) || DEFAULTS.ftp_port,
    });
    probe.value = data;
    const [first] = data.users;
    if (first && !data.users.some((u) => u.id === draft.value.ps3_user)) {
      draft.value.ps3_user = first.id;
    }
  } catch (error) {
    probeError.value = errorMessage(error);
  } finally {
    probing.value = false;
  }
}

// Reopening resets the form, so a cancelled edit does not carry over. An
// edited console is tested right away, so its profiles show with their names.
watch(
  () => props.modelValue,
  (open) => {
    if (!open) return;
    draft.value = draftOf(props.device);
    probe.value = null;
    probeError.value = null;
    if (props.device) void testConnection();
  },
  { immediate: true },
);

function close(): void {
  emit("update:modelValue", false);
}

function submit(): void {
  const d = draft.value;
  if (!canSubmit.value || !d.ps3_user) return;
  emit("submit", {
    console: d.console,
    name: d.name.trim(),
    ip_address: d.ip_address.trim(),
    ftp_port: Number(d.ftp_port),
    ps3_user: d.ps3_user,
    poll_interval_minutes: Number(d.poll_interval_minutes),
    keep_versions: Number(d.keep_versions),
  });
}
</script>

<template>
  <RDialog
    :model-value="modelValue"
    icon="mdi-gamepad-variant-outline"
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
      <span>
        {{ device ? t("settings.console-edit") : t("settings.console-add") }}
      </span>
    </template>

    <template #content>
      <RForm v-model="valid" class="r-console-dialog" @submit="submit">
        <RSelect
          v-model="draft.console"
          :items="consoles"
          :label="t('settings.console-kind')"
          prefix-label="stacked"
          :disabled="!!device"
          hide-details
        />

        <RAlert
          type="info"
          variant="translucent"
          density="compact"
          :text="t('settings.console-dialog-intro')"
        />

        <RTextField
          v-model="draft.name"
          :label="t('common.name')"
          prefix-label="stacked"
          :rules="rules.required"
          :maxlength="255"
          required
        />

        <div class="r-console-dialog__row">
          <!-- eslint-disable vuejs-accessibility/no-autofocus -- the address is what a new console needs first -->
          <RTextField
            v-model="draft.ip_address"
            class="r-console-dialog__grow"
            :label="t('settings.console-ip-address')"
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
            class="r-console-dialog__narrow"
            type="number"
            min="1"
            max="65535"
            :label="t('settings.console-ftp-port')"
            prefix-label="stacked"
            :rules="rules.port"
            required
          />
        </div>

        <div class="r-console-dialog__probe">
          <RBtn
            variant="translucent"
            prepend-icon="mdi-lan-connect"
            :loading="probing"
            :disabled="!canProbe"
            @click="testConnection"
          >
            {{ t("settings.console-test") }}
          </RBtn>
          <RAlert
            v-if="probeAlert"
            class="r-console-dialog__grow"
            :type="probeAlert.type"
            variant="translucent"
            density="compact"
            :text="probeAlert.text"
            role="status"
          />
        </div>

        <RSelect
          v-model="draft.ps3_user"
          :items="users"
          :label="t('settings.console-user')"
          :hint="t('settings.console-user-hint')"
          prefix-label="stacked"
          :disabled="!users.length"
          :rules="rules.user"
          required
        />

        <div class="r-console-dialog__row">
          <RTextField
            v-model="draft.poll_interval_minutes"
            class="r-console-dialog__grow"
            type="number"
            min="1"
            max="1440"
            :label="t('settings.console-interval')"
            prefix-label="stacked"
            :rules="rules.interval"
            required
          />
          <RTextField
            v-model="draft.keep_versions"
            class="r-console-dialog__grow"
            type="number"
            min="1"
            max="100"
            :label="t('settings.console-keep-versions')"
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
.r-console-dialog {
  display: flex;
  flex-direction: column;
  gap: var(--r-space-3);
}

.r-console-dialog__row {
  display: flex;
  gap: var(--r-space-3);
  align-items: flex-start;
}

.r-console-dialog__grow {
  flex: 1 1 0;
  min-width: 0;
}

.r-console-dialog__narrow {
  flex: 0 0 112px;
}

.r-console-dialog__probe {
  display: flex;
  gap: var(--r-space-3);
  align-items: center;
  flex-wrap: wrap;
}
</style>

<style>
html[data-bp~="xs"] .r-console-dialog__row {
  flex-direction: column;
  align-items: stretch;
}

html[data-bp~="xs"] .r-console-dialog__narrow {
  flex-basis: auto;
}
</style>
