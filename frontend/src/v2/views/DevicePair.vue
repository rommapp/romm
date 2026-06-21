<script setup lang="ts">
/**
 * Device authorization approval target (RFC 8628 style). A signed-in user
 * lands here from a pairing link (`/pair/device?user_code=…`), reviews the
 * requesting device, then approves it — granting a scoped, device-bound
 * client token — or denies the request.
 *
 * v2-only: rendered inside {@link DevicePairShell}, which owns the
 * AuthLayout-style chrome and the `.r-v2` token scope.
 */
import { RBtn, RChip, RIcon, RSelect, RSpinner, RTextField } from "@v2/lib";
import type { AxiosError } from "axios";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import deviceAuthApi, {
  type DeviceAuthPendingSchema,
} from "@/services/api/device-auth";

type ApiError = AxiosError<{ detail?: string }>;

type Status =
  | "loading"
  | "ready"
  | "submitting"
  | "approved"
  | "denied"
  | "error";

const route = useRoute();
const { t } = useI18n();

const userCode = computed(() => (route.query.user_code as string) || "");

const status = ref<Status>("loading");
const errorMessage = ref("");
const pending = ref<DeviceAuthPendingSchema | null>(null);

const editedDeviceName = ref("");
const selectedScopes = ref<string[]>([]);
const expiresIn = ref<string>("never");

const EXPIRY_OPTIONS = computed(() => [
  { value: "30d", label: t("settings.client-token-expiry-30d") },
  { value: "90d", label: t("settings.client-token-expiry-90d") },
  { value: "1y", label: t("settings.client-token-expiry-1y") },
  { value: "never", label: t("settings.client-token-expiry-never") },
]);

const disallowedScopes = computed(() => {
  if (!pending.value) return [];
  const allowed = new Set(pending.value.allowed_scopes);
  return pending.value.requested_scopes.filter((s) => !allowed.has(s));
});

function toggleScope(scope: string) {
  const idx = selectedScopes.value.indexOf(scope);
  if (idx === -1) selectedScopes.value.push(scope);
  else selectedScopes.value.splice(idx, 1);
}

onMounted(async () => {
  if (!userCode.value) {
    status.value = "error";
    errorMessage.value = t("settings.device-auth-no-code");
    return;
  }

  try {
    const { data } = await deviceAuthApi.getPending(userCode.value);
    pending.value = data;
    editedDeviceName.value = data.name;
    selectedScopes.value = [...data.allowed_scopes];
    status.value = "ready";
  } catch (err) {
    status.value = "error";
    const e = err as ApiError;
    const code = e.response?.status;
    if (code === 404) {
      errorMessage.value = t("settings.device-auth-code-expired");
    } else if (code === 410) {
      errorMessage.value = t("settings.device-auth-code-already-handled");
    } else {
      errorMessage.value =
        e.response?.data?.detail || t("settings.device-auth-fetch-failed");
    }
  }
});

const AUTO_CLOSE_SECONDS = 3;
const closeCountdown = ref<number>(AUTO_CLOSE_SECONDS);
const closeIntervalId = ref<number | null>(null);

function scheduleAutoClose() {
  closeCountdown.value = AUTO_CLOSE_SECONDS;
  closeIntervalId.value = window.setInterval(() => {
    closeCountdown.value -= 1;
    if (closeCountdown.value <= 0) {
      if (closeIntervalId.value !== null) {
        window.clearInterval(closeIntervalId.value);
        closeIntervalId.value = null;
      }
      window.close();
    }
  }, 1000);
}

onBeforeUnmount(() => {
  if (closeIntervalId.value !== null) {
    window.clearInterval(closeIntervalId.value);
    closeIntervalId.value = null;
  }
});

async function approve() {
  if (!pending.value || selectedScopes.value.length === 0) return;
  status.value = "submitting";
  try {
    await deviceAuthApi.approve({
      userCode: userCode.value,
      approvedScopes: selectedScopes.value,
      deviceName: editedDeviceName.value || undefined,
      expiresIn: expiresIn.value,
    });
    status.value = "approved";
    scheduleAutoClose();
  } catch (err) {
    status.value = "error";
    const e = err as ApiError;
    errorMessage.value =
      e.response?.data?.detail || t("settings.device-auth-approve-failed");
  }
}

async function deny() {
  status.value = "submitting";
  try {
    await deviceAuthApi.deny(userCode.value);
    status.value = "denied";
  } catch (err) {
    status.value = "error";
    const e = err as ApiError;
    errorMessage.value =
      e.response?.data?.detail || t("settings.device-auth-deny-failed");
  }
}
</script>

<template>
  <div class="r-v2-devpair">
    <!-- Loading -->
    <div v-if="status === 'loading'" class="r-v2-devpair__state">
      <RSpinner :size="48" :width="3" />
      <p class="r-v2-devpair__body">{{ t("settings.device-auth-loading") }}</p>
    </div>

    <!-- Error -->
    <div v-else-if="status === 'error'" class="r-v2-devpair__state">
      <div class="r-v2-devpair__icon-wrap r-v2-devpair__icon-wrap--danger">
        <RIcon icon="mdi-alert-circle" size="32" />
      </div>
      <p class="r-v2-devpair__body">{{ errorMessage }}</p>
    </div>

    <!-- Approved -->
    <div v-else-if="status === 'approved'" class="r-v2-devpair__state">
      <div class="r-v2-devpair__icon-wrap r-v2-devpair__icon-wrap--success">
        <RIcon icon="mdi-check-circle" size="32" />
      </div>
      <h2 class="r-v2-devpair__title">
        {{ t("settings.device-auth-approved-title") }}
      </h2>
      <p class="r-v2-devpair__body">
        {{ t("settings.device-auth-approved-body") }}
      </p>
      <p v-if="closeCountdown > 0" class="r-v2-devpair__hint">
        {{ t("settings.device-auth-auto-close", { seconds: closeCountdown }) }}
      </p>
    </div>

    <!-- Denied -->
    <div v-else-if="status === 'denied'" class="r-v2-devpair__state">
      <div class="r-v2-devpair__icon-wrap r-v2-devpair__icon-wrap--warning">
        <RIcon icon="mdi-cancel" size="32" />
      </div>
      <h2 class="r-v2-devpair__title">
        {{ t("settings.device-auth-denied-title") }}
      </h2>
      <p class="r-v2-devpair__body">
        {{ t("settings.device-auth-denied-body") }}
      </p>
    </div>

    <!-- Ready / submitting -->
    <div v-else class="r-v2-devpair__form">
      <div class="r-v2-devpair__header">
        <div class="r-v2-devpair__icon-wrap">
          <RIcon icon="mdi-devices" size="32" />
        </div>
        <h2 class="r-v2-devpair__title">
          {{ t("settings.device-auth-heading") }}
        </h2>
        <p class="r-v2-devpair__body">
          {{ t("settings.device-auth-subheading") }}
        </p>
      </div>

      <div class="r-v2-devpair__chips">
        <RChip v-if="pending?.client" size="small" color="primary">
          {{ pending.client }}
        </RChip>
        <RChip v-if="pending?.platform" size="small" variant="outlined">
          {{ pending.platform }}
        </RChip>
        <RChip v-if="pending?.client_version" size="small" variant="text">
          v{{ pending.client_version }}
        </RChip>
      </div>

      <p
        v-if="pending?.client_device_identifier"
        class="r-v2-devpair__identifier"
      >
        {{ pending.client_device_identifier }}
      </p>

      <RTextField
        v-model="editedDeviceName"
        :label="t('settings.device-auth-device-name')"
        variant="outlined"
        density="comfortable"
      />

      <div class="r-v2-devpair__scopes">
        <p class="r-v2-devpair__label">
          {{ t("settings.device-auth-scopes-label") }}
        </p>
        <div class="r-v2-devpair__scope-grid">
          <RChip
            v-for="scope in pending?.allowed_scopes ?? []"
            :key="scope"
            size="small"
            role="checkbox"
            tabindex="0"
            :aria-checked="selectedScopes.includes(scope)"
            :color="selectedScopes.includes(scope) ? 'primary' : undefined"
            :variant="selectedScopes.includes(scope) ? 'flat' : 'outlined'"
            :prepend-icon="
              selectedScopes.includes(scope) ? 'mdi-check' : undefined
            "
            class="r-v2-devpair__scope"
            @click="toggleScope(scope)"
            @keydown.enter.prevent="toggleScope(scope)"
            @keydown.space.prevent="toggleScope(scope)"
          >
            {{ scope }}
          </RChip>
        </div>
      </div>

      <div v-if="disallowedScopes.length > 0" class="r-v2-devpair__scopes">
        <p class="r-v2-devpair__label">
          {{ t("settings.device-auth-disallowed-label") }}
        </p>
        <div class="r-v2-devpair__scope-grid">
          <RChip
            v-for="scope in disallowedScopes"
            :key="scope"
            size="small"
            variant="outlined"
            color="warning"
            disabled
          >
            {{ scope }}
          </RChip>
        </div>
      </div>

      <RSelect
        v-model="expiresIn"
        :label="t('settings.device-auth-expires-in')"
        :items="EXPIRY_OPTIONS"
        item-title="label"
        item-value="value"
        variant="outlined"
        density="comfortable"
      />

      <div class="r-v2-devpair__actions">
        <RBtn variant="text" :disabled="status === 'submitting'" @click="deny">
          {{ t("settings.device-auth-deny") }}
        </RBtn>
        <RBtn
          variant="flat"
          color="primary"
          :loading="status === 'submitting'"
          :disabled="selectedScopes.length === 0"
          @click="approve"
        >
          {{ t("settings.device-auth-approve") }}
        </RBtn>
      </div>
    </div>
  </div>
</template>

<style scoped>
.r-v2-devpair {
  background: color-mix(
    in srgb,
    var(--r-color-canvas-bg-deep) 72%,
    transparent
  );
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(22px);
  -webkit-backdrop-filter: blur(22px);
  padding: 32px;
  box-shadow:
    0 22px 60px color-mix(in srgb, black 55%, transparent),
    0 2px 6px color-mix(in srgb, black 30%, transparent);
}

.r-v2-devpair__state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.r-v2-devpair__form {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.r-v2-devpair__header {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  text-align: center;
}

.r-v2-devpair__icon-wrap {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--r-color-brand-primary) 15%, transparent);
  color: var(--r-color-brand-primary);
}
.r-v2-devpair__icon-wrap--danger {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 15%,
    transparent
  );
  color: var(--r-color-danger-fg);
}
.r-v2-devpair__icon-wrap--success {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-success) 15%,
    transparent
  );
  color: var(--r-color-success);
}
.r-v2-devpair__icon-wrap--warning {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-warning) 15%,
    transparent
  );
  color: var(--r-color-warning);
}

.r-v2-devpair__title {
  margin: 0;
  color: var(--r-color-fg);
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
}

.r-v2-devpair__body {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-md);
}

.r-v2-devpair__hint {
  margin: 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}

.r-v2-devpair__chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.r-v2-devpair__identifier {
  margin: 0;
  font-family: var(--r-font-family-mono);
  font-size: var(--r-font-size-sm);
  color: var(--r-color-fg-muted);
  word-break: break-all;
}

.r-v2-devpair__scopes {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.r-v2-devpair__label {
  margin: 0;
  color: var(--r-color-fg-secondary);
  font-size: var(--r-font-size-sm);
}

.r-v2-devpair__scope-grid {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  max-height: 168px;
  overflow-y: auto;
}

.r-v2-devpair__scope {
  cursor: pointer;
}
.r-v2-devpair__scope:focus-visible {
  outline: 2px solid var(--r-color-brand-primary);
  outline-offset: 2px;
}

.r-v2-devpair__actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  margin-top: 8px;
}
</style>
