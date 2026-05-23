^
<script setup lang="ts">
// Setup — three-step first-run wizard. Orchestrates library info loading,
// platform selection, admin user creation, and metadata source review.
// The wizard owns all wizard-level state (current step, selection set,
// admin form, async flight); the per-step components are pure UI that
// emit input changes back to the orchestrator.
import { RBtn, RImg, RSpinner } from "@v2/lib";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRouter } from "vue-router";
import { refetchCSRFToken } from "@/services/api";
import setupApi from "@/services/api/setup";
import type { SetupLibraryInfo } from "@/services/api/setup";
import userApi from "@/services/api/user";
import storeHeartbeat from "@/stores/heartbeat";
import SetupStepAdmin from "@/v2/components/Auth/SetupStepAdmin.vue";
import type { AdminUserDraft } from "@/v2/components/Auth/SetupStepAdmin.vue";
import SetupStepMetadata from "@/v2/components/Auth/SetupStepMetadata.vue";
import SetupStepPlatforms from "@/v2/components/Auth/SetupStepPlatforms.vue";
import SetupStepper from "@/v2/components/Auth/SetupStepper.vue";
import { useSnackbar } from "@/v2/composables/useSnackbar";

const { t } = useI18n();
const router = useRouter();
const heartbeat = storeHeartbeat();
const snackbar = useSnackbar();

const TOTAL_STEPS = 3;

const step = ref<1 | 2 | 3>(1);

// Step 1 — library + platforms
const libraryInfo = ref<SetupLibraryInfo | null>(null);
const loadingLibrary = ref(false);
const selectedNewPlatforms = ref<string[]>([]);

// Step 2 — admin user
const adminUser = ref<AdminUserDraft>({
  username: "",
  email: "",
  password: "",
  repeatPassword: "",
});
const adminFormValid = ref(false);

// Step 3 — metadata (purely informational)

// Final submission
const submitting = ref(false);

const stepTitle = computed(() => {
  switch (step.value) {
    case 1:
      return t("setup.library-structure-step");
    case 2:
      return t("setup.admin-user-step");
    case 3:
      return t("setup.check-metadata-step");
    default:
      return "";
  }
});

const canProceed = computed(() => {
  if (step.value === 1) return !loadingLibrary.value;
  if (step.value === 2) return adminFormValid.value;
  return true;
});

const isFirstStep = computed(() => step.value === 1);
const isLastStep = computed(() => step.value === TOTAL_STEPS);

async function loadLibraryInfo() {
  loadingLibrary.value = true;
  try {
    const { data } = await setupApi.getLibraryInfo();
    libraryInfo.value = data;
  } catch (err) {
    const error = err as {
      response?: { data?: { detail?: string } };
      message?: string;
    };
    snackbar.error(
      `${t("setup.loading-library-failed")}: ${
        error.response?.data?.detail ?? error.message ?? ""
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    loadingLibrary.value = false;
  }
}

function prev() {
  if (step.value > 1) step.value = (step.value - 1) as 1 | 2 | 3;
}

function next() {
  if (!canProceed.value) return;
  if (step.value < TOTAL_STEPS) {
    step.value = (step.value + 1) as 1 | 2 | 3;
    return;
  }
  void finishWizard();
}

async function finishWizard() {
  submitting.value = true;
  try {
    if (selectedNewPlatforms.value.length > 0) {
      const { data } = await setupApi.createPlatforms(
        selectedNewPlatforms.value,
      );
      snackbar.success(data.message, { icon: "mdi-check-circle" });
    }

    await userApi.createUser({
      username: adminUser.value.username,
      email: adminUser.value.email,
      password: adminUser.value.password,
      role: "admin",
    });

    await refetchCSRFToken();
    await heartbeat.fetchHeartbeat();
    router.push({ name: "login" });
  } catch (err) {
    const error = err as {
      response?: { data?: { detail?: string }; statusText?: string };
      message?: string;
    };
    snackbar.error(
      `${t("setup.creating-platforms-failed")}: ${
        error.response?.data?.detail ??
        error.response?.statusText ??
        error.message ??
        ""
      }`,
      { icon: "mdi-close-circle" },
    );
  } finally {
    submitting.value = false;
  }
}

onMounted(loadLibraryInfo);
</script>

<template>
  <div class="r-v2-setup">
    <header class="r-v2-setup__header">
      <RImg
        src="/assets/isotipo.svg"
        :width="56"
        class="r-v2-setup__logo"
        alt="RomM"
      />
      <SetupStepper :current="step" :total="TOTAL_STEPS" />
      <div class="r-v2-setup__title">
        <span class="r-v2-setup__step-of">
          {{ t("setup.step-of", { current: step, total: TOTAL_STEPS }) }}
        </span>
        <h2>{{ stepTitle }}</h2>
      </div>
    </header>

    <div class="r-v2-setup__body">
      <div v-if="loadingLibrary && step === 1" class="r-v2-setup__loading">
        <RSpinner />
        <span>{{ t("setup.loading-library") }}</span>
      </div>

      <SetupStepPlatforms
        v-else-if="step === 1 && libraryInfo"
        :library-info="libraryInfo"
        v-model:selected-new-platforms="selectedNewPlatforms"
      />

      <SetupStepAdmin
        v-else-if="step === 2"
        v-model="adminUser"
        v-model:valid="adminFormValid"
        @submit="next"
      />

      <SetupStepMetadata v-else-if="step === 3" />
    </div>

    <footer class="r-v2-setup__footer">
      <RBtn
        variant="text"
        :disabled="isFirstStep || submitting"
        prepend-icon="mdi-chevron-left"
        @click="prev"
      >
        {{ t("setup.previous") }}
      </RBtn>

      <div class="r-v2-setup__footer-spacer" />

      <RBtn
        variant="flat"
        color="primary"
        :append-icon="isLastStep ? 'mdi-check' : 'mdi-chevron-right'"
        :loading="submitting"
        :disabled="!canProceed || submitting"
        @click="next"
      >
        {{ isLastStep ? t("setup.finish") : t("setup.next") }}
      </RBtn>
    </footer>
  </div>
</template>

<style scoped>
.r-v2-setup {
  width: 100%;
  max-width: 1080px;
  height: min(86dvh, 880px);
  display: flex;
  flex-direction: column;
  background: linear-gradient(
    180deg,
    color-mix(in srgb, var(--r-color-canvas-bg-deep) 65%, transparent) 0%,
    color-mix(in srgb, var(--r-color-canvas-bg-deep) 65%, transparent) 100%
  );
  backdrop-filter: blur(20px);
  border: 1px solid var(--r-color-border);
  border-radius: var(--r-radius-lg);
  box-shadow: var(--r-elev-4);
  overflow: hidden;
}

.r-v2-setup__header {
  display: grid;
  grid-template-columns: 1fr auto 1fr;
  align-items: center;
  gap: var(--r-space-4);
  padding: var(--r-space-5) var(--r-space-6) var(--r-space-4);
  border-bottom: 1px solid var(--r-color-border);
}

.r-v2-setup__logo {
  filter: drop-shadow(
    0 0 16px color-mix(in srgb, var(--r-color-brand-primary) 30%, transparent)
  );
  justify-self: start;
}

.r-v2-setup__title {
  grid-column: 1 / -1;
  text-align: center;
  margin-top: var(--r-space-3);
}

.r-v2-setup__title h2 {
  margin: 0;
  font-size: var(--r-font-size-lg);
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg);
}

.r-v2-setup__step-of {
  display: block;
  font-size: var(--r-font-size-xs);
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--r-color-fg-muted);
  margin-bottom: var(--r-space-1);
}

.r-v2-setup__body {
  flex: 1 1 auto;
  min-height: 0;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  padding: var(--r-space-5) var(--r-space-6);
}

.r-v2-setup__loading {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--r-space-4);
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
}

.r-v2-setup__footer {
  display: flex;
  align-items: center;
  gap: var(--r-space-3);
  padding: var(--r-space-4) var(--r-space-6);
  border-top: 1px solid var(--r-color-border);
}

.r-v2-setup__footer-spacer {
  flex: 1 1 auto;
}
</style>
