<script setup lang="ts">
import type { AxiosError } from "axios";
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";
import deviceAuthApi, {
  type DeviceAuthPendingSchema,
} from "@/services/api/device-auth";

type ApiError = AxiosError<{ detail?: string }>;

const route = useRoute();
const { t } = useI18n();

type Status =
  | "loading"
  | "ready"
  | "submitting"
  | "approved"
  | "denied"
  | "error";

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

function scheduleAutoClose() {
  closeCountdown.value = AUTO_CLOSE_SECONDS;
  closeIntervalId.value = window.setInterval(() => {
    closeCountdown.value -= 1;
    if (closeCountdown.value <= 0) {
      if (closeIntervalId.value !== null) {
        window.clearInterval(closeIntervalId.value);
        closeIntervalId.value = null;
      }
      // window.close() is a no-op when the tab wasn't opened by script;
      // the "you can close this tab" caption covers that case.
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
  <v-app>
    <v-main
      class="d-flex align-center justify-center"
      style="min-height: 100dvh"
    >
      <v-card max-width="500" class="pa-6" variant="outlined">
        <!-- Loading -->
        <template v-if="status === 'loading'">
          <div class="text-center">
            <v-progress-circular indeterminate size="48" class="mb-4" />
            <p class="text-body-1">
              {{ t("settings.device-auth-loading") }}
            </p>
          </div>
        </template>

        <!-- Error -->
        <template v-else-if="status === 'error'">
          <div class="text-center">
            <v-icon size="64" color="romm-red" class="mb-4">
              mdi-alert-circle
            </v-icon>
            <p class="text-body-1">
              {{ errorMessage }}
            </p>
          </div>
        </template>

        <!-- Approved -->
        <template v-else-if="status === 'approved'">
          <div class="text-center">
            <v-icon size="64" color="romm-green" class="mb-4">
              mdi-check-circle
            </v-icon>
            <p class="text-h6 mb-2">
              {{ t("settings.device-auth-approved-title") }}
            </p>
            <p class="text-body-2 text-medium-emphasis">
              {{ t("settings.device-auth-approved-body") }}
            </p>
            <p class="text-caption text-medium-emphasis mt-3">
              {{
                t("settings.device-auth-auto-close", {
                  seconds: closeCountdown,
                })
              }}
            </p>
          </div>
        </template>

        <!-- Denied -->
        <template v-else-if="status === 'denied'">
          <div class="text-center">
            <v-icon size="64" color="warning" class="mb-4"> mdi-cancel </v-icon>
            <p class="text-h6 mb-2">
              {{ t("settings.device-auth-denied-title") }}
            </p>
            <p class="text-body-2 text-medium-emphasis">
              {{ t("settings.device-auth-denied-body") }}
            </p>
          </div>
        </template>

        <!-- Ready / submitting -->
        <template v-else>
          <div class="text-center mb-4">
            <v-icon size="48" class="mb-2"> mdi-devices </v-icon>
            <h2 class="text-h5">
              {{ t("settings.device-auth-heading") }}
            </h2>
            <p class="text-body-2 text-medium-emphasis">
              {{ t("settings.device-auth-subheading") }}
            </p>
          </div>

          <v-text-field
            v-model="editedDeviceName"
            :label="t('settings.device-auth-device-name')"
            variant="outlined"
            density="comfortable"
            class="mb-2"
          />

          <div class="d-flex flex-wrap ga-2 mb-4">
            <v-chip v-if="pending?.client" size="small" color="primary">
              {{ pending.client }}
            </v-chip>
            <v-chip v-if="pending?.platform" size="small">
              {{ pending.platform }}
            </v-chip>
            <v-chip v-if="pending?.client_version" size="small" variant="text">
              v{{ pending.client_version }}
            </v-chip>
          </div>

          <p
            v-if="pending?.client_device_identifier"
            class="text-caption text-medium-emphasis mb-4"
            style="font-family: monospace"
          >
            {{ pending.client_device_identifier }}
          </p>

          <p class="text-body-2 mb-2">
            {{ t("settings.device-auth-scopes-label") }}
          </p>
          <v-chip-group v-model="selectedScopes" column multiple>
            <v-chip
              v-for="scope in pending?.allowed_scopes ?? []"
              :key="scope"
              :value="scope"
              filter
              variant="outlined"
            >
              {{ scope }}
            </v-chip>
          </v-chip-group>

          <!-- Scopes the device requested but the user lacks -->
          <div v-if="disallowedScopes.length > 0" class="mb-2">
            <p class="text-caption text-medium-emphasis">
              {{ t("settings.device-auth-disallowed-label") }}
            </p>
            <div class="d-flex flex-wrap ga-1">
              <v-chip
                v-for="scope in disallowedScopes"
                :key="scope"
                size="small"
                variant="outlined"
                color="warning"
                disabled
              >
                {{ scope }}
              </v-chip>
            </div>
          </div>

          <v-select
            v-model="expiresIn"
            :label="t('settings.device-auth-expires-in')"
            :items="EXPIRY_OPTIONS"
            item-title="label"
            item-value="value"
            variant="outlined"
            density="comfortable"
            class="mt-4 mb-2"
          />

          <div class="d-flex justify-end mt-4">
            <v-btn-group divided density="compact">
              <v-btn
                class="bg-toplayer text-romm-red"
                :disabled="status === 'submitting'"
                @click="deny"
              >
                {{ t("settings.device-auth-deny") }}
              </v-btn>
              <v-btn
                class="bg-toplayer text-primary"
                :loading="status === 'submitting'"
                :disabled="selectedScopes.length === 0"
                @click="approve"
              >
                {{ t("settings.device-auth-approve") }}
              </v-btn>
            </v-btn-group>
          </div>
        </template>
      </v-card>
    </v-main>
  </v-app>
</template>
