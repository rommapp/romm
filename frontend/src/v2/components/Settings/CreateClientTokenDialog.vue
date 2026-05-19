<script setup lang="ts">
// CreateClientTokenDialog — v2-native rebuild of v1's
// `Settings/ClientApiTokens/Dialog/CreateClientToken.vue`. Single dialog
// driving the create + regenerate flows through four steps:
//   1. config   — name + expiry + scope picker
//   2. delivery — choose copy or pair
//   3. copy     — shows the raw token with a copy button
//   4. pair     — QR + 4-digit code + countdown; polls until claimed
//
// Regenerate jumps straight to step 2 with the new token already
// generated. The dialog responds to the same emitter events the v1
// dialog used so call-sites don't change.
import {
  RBtn,
  RCheckbox,
  RIcon,
  RProgressCircular,
  RSelect,
  RTextField,
} from "@v2/lib";
import type { Emitter } from "mitt";
import qrcode from "qrcode";
import { computed, inject, nextTick, onBeforeUnmount, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import clientTokenApi, {
  type ClientTokenSchema,
} from "@/services/api/client-token";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";
import { useSnackbar } from "@/v2/composables/useSnackbar";
import RDialog from "@/v2/lib/overlays/RDialog/RDialog.vue";

defineOptions({ inheritAttrs: false });

const emit = defineEmits<{ created: [] }>();

const { t } = useI18n();
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");
const snackbar = useSnackbar();

type Step = "config" | "delivery" | "copy" | "pair";
type PairStatus = "pending" | "claimed" | "expired";

const show = ref(false);
const step = ref<Step>("config");
const loading = ref(false);

const tokenName = ref("");
const selectedScopes = ref<string[]>([]);
const selectedExpiry = ref("never");
const rawToken = ref("");
const tokenId = ref<number | null>(null);

const pairCode = ref("");
const pairCountdown = ref(0);
const pairStatus = ref<PairStatus>("pending");
const pairLoading = ref(false);
let pairTimer: ReturnType<typeof setInterval> | null = null;

const isRegenerate = ref(false);
const regenerateToken = ref<ClientTokenSchema | null>(null);

const expiryOptions = computed(() => [
  { title: t("settings.client-token-expiry-30d"), value: "30d" },
  { title: t("settings.client-token-expiry-90d"), value: "90d" },
  { title: t("settings.client-token-expiry-1y"), value: "1y" },
  { title: t("settings.client-token-expiry-never"), value: "never" },
]);

const userScopes = computed(() => auth.scopes);

interface ScopeGroup {
  label: string;
  scopes: string[];
}

const scopeColumns = computed<{ left: ScopeGroup[]; right: ScopeGroup[] }>(
  () => {
    const sortScopes = (scopes: string[]) => {
      const prefixOrder = new Map<string, number>();
      scopes.forEach((s) => {
        const prefix = s.split(".").slice(0, -1).join(".");
        if (!prefixOrder.has(prefix)) prefixOrder.set(prefix, prefixOrder.size);
      });
      return [...scopes].sort((a, b) => {
        const pa = a.split(".").slice(0, -1).join(".");
        const pb = b.split(".").slice(0, -1).join(".");
        if (pa !== pb)
          return (prefixOrder.get(pa) ?? 0) - (prefixOrder.get(pb) ?? 0);
        return a.localeCompare(b);
      });
    };

    const personal = sortScopes(
      userScopes.value.filter((s) =>
        /^(me|assets|devices|roms\.user)\./.test(s),
      ),
    );
    const admin = sortScopes(
      userScopes.value.filter((s) => /^(users|tasks)\./.test(s)),
    );
    const library = sortScopes(
      userScopes.value.filter(
        (s) =>
          /^(platforms|firmware|collections)\./.test(s) ||
          (/^roms\./.test(s) && !/^roms\.user\./.test(s)),
      ),
    );
    const grouped = new Set([...personal, ...admin, ...library]);
    const other = userScopes.value.filter((s) => !grouped.has(s));

    const left: ScopeGroup[] = [];
    if (personal.length > 0) left.push({ label: "Personal", scopes: personal });
    if (admin.length > 0) left.push({ label: "Administration", scopes: admin });
    if (other.length > 0) left.push({ label: "Other", scopes: other });

    const right: ScopeGroup[] = [];
    if (library.length > 0) right.push({ label: "Library", scopes: library });
    return { left, right };
  },
);

const configValid = computed(
  () => tokenName.value.trim().length > 0 && selectedScopes.value.length > 0,
);

function isScopeSelected(scope: string): boolean {
  return selectedScopes.value.includes(scope);
}

function toggleScope(scope: string, value: boolean | null) {
  const set = new Set(selectedScopes.value);
  if (value) set.add(scope);
  else set.delete(scope);
  selectedScopes.value = [...set];
}

const formattedPairCode = computed(() => {
  const c = pairCode.value;
  return c ? `${c.slice(0, 4)}-${c.slice(4)}` : "";
});

const dialogTitle = computed(() => {
  if (step.value === "config") return "Create new API token";
  if (step.value === "delivery")
    return isRegenerate.value ? "Regenerate token" : "Deliver token";
  if (step.value === "copy") return "Copy token";
  return "Pair device";
});

emitter?.on("showCreateClientTokenDialog", () => {
  resetDialog();
  isRegenerate.value = false;
  regenerateToken.value = null;
  selectedScopes.value = [...userScopes.value];
  show.value = true;
});

emitter?.on("showRegenerateClientTokenDialog", (token) => {
  resetDialog();
  isRegenerate.value = true;
  regenerateToken.value = token;
  tokenName.value = token.name;
  selectedScopes.value = [...token.scopes];
  step.value = "delivery";
  show.value = true;
  void doRegenerate();
});

function resetDialog() {
  step.value = "config";
  tokenName.value = "";
  selectedScopes.value = [];
  selectedExpiry.value = "never";
  rawToken.value = "";
  tokenId.value = null;
  pairCode.value = "";
  pairStatus.value = "pending";
  pairCountdown.value = 0;
  loading.value = false;
  pairLoading.value = false;
  clearPairTimer();
}

function clearPairTimer() {
  if (pairTimer) {
    clearInterval(pairTimer);
    pairTimer = null;
  }
}

async function createToken() {
  loading.value = true;
  try {
    const { data } = await clientTokenApi.createToken({
      name: tokenName.value.trim(),
      scopes: selectedScopes.value,
      expires_in:
        selectedExpiry.value === "never" ? undefined : selectedExpiry.value,
    });
    rawToken.value = data.raw_token;
    tokenId.value = data.id;
    step.value = "delivery";
    emit("created");
    snackbar.success(t("settings.client-token-created"), {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    const e = err as { response?: { data?: { detail?: string } } };
    snackbar.error(e?.response?.data?.detail || "Failed to create token", {
      icon: "mdi-close-circle",
    });
  } finally {
    loading.value = false;
  }
}

async function doRegenerate() {
  if (!regenerateToken.value) return;
  loading.value = true;
  try {
    const { data } = await clientTokenApi.regenerateToken(
      regenerateToken.value.id,
    );
    rawToken.value = data.raw_token;
    tokenId.value = data.id;
    emit("created");
    snackbar.success(t("settings.client-token-regenerated"), {
      icon: "mdi-check-bold",
    });
  } catch (err) {
    const e = err as { response?: { data?: { detail?: string } } };
    snackbar.error(e?.response?.data?.detail || "Failed to regenerate token", {
      icon: "mdi-close-circle",
    });
    show.value = false;
  } finally {
    loading.value = false;
  }
}

async function copyToken() {
  try {
    await navigator.clipboard.writeText(rawToken.value);
    snackbar.success(t("settings.client-token-copied"), {
      icon: "mdi-check-bold",
    });
  } catch {
    /* ignore — clipboard unavailable */
  }
}

async function startPairing() {
  if (!tokenId.value) return;
  step.value = "pair";
  pairLoading.value = true;
  pairStatus.value = "pending";
  try {
    const { data } = await clientTokenApi.pairToken(tokenId.value);
    pairCode.value = data.code;
    pairCountdown.value = data.expires_in;
    pairLoading.value = false;
    await nextTick();
    renderQR(data.code);
    startPairPolling();
  } catch (err) {
    pairLoading.value = false;
    const e = err as { response?: { data?: { detail?: string } } };
    snackbar.error(
      e?.response?.data?.detail || "Failed to generate pairing code",
      { icon: "mdi-close-circle" },
    );
    step.value = "delivery";
  }
}

function startPairPolling() {
  clearPairTimer();
  pairTimer = setInterval(async () => {
    pairCountdown.value -= 1;
    if (pairCountdown.value <= 0) {
      clearPairTimer();
      pairStatus.value = "expired";
      return;
    }
    if (pairCountdown.value % 3 === 0) {
      try {
        await clientTokenApi.pollPairStatus(pairCode.value);
      } catch {
        // The poll throws when the code has been claimed (4xx) — treat
        // it as "claimed" if there's still time, "expired" otherwise.
        clearPairTimer();
        if (pairCountdown.value > 0) {
          pairStatus.value = "claimed";
          snackbar.success(t("settings.client-token-pair-claimed"), {
            icon: "mdi-check-bold",
          });
        } else {
          pairStatus.value = "expired";
        }
      }
    }
  }, 1000);
}

async function regeneratePairCode() {
  if (!tokenId.value) return;
  pairStatus.value = "pending";
  pairLoading.value = true;
  try {
    const { data } = await clientTokenApi.pairToken(tokenId.value);
    pairCode.value = data.code;
    pairCountdown.value = data.expires_in;
    pairLoading.value = false;
    await nextTick();
    renderQR(data.code);
    startPairPolling();
  } catch (err) {
    pairLoading.value = false;
    const e = err as { response?: { data?: { detail?: string } } };
    snackbar.error(e?.response?.data?.detail || "Failed to regenerate code", {
      icon: "mdi-close-circle",
    });
  }
}

function renderQR(code: string) {
  const displayCode = `${code.slice(0, 4)}-${code.slice(4)}`;
  const pairUrl = `${window.location.origin}/pair?code=${displayCode}`;
  const canvas = document.getElementById(
    "r-v2-pair-qr-code",
  ) as HTMLCanvasElement | null;
  if (!canvas) return;

  const isWide = window.innerWidth >= 1280;
  const size = isWide ? 250 : 200;
  qrcode.toCanvas(
    canvas,
    pairUrl,
    { margin: 2, width: size, errorCorrectionLevel: "H" },
    () => {
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      const logo = new Image();
      logo.src = "/assets/logos/romm_logo_xbox_one_circle.svg";
      logo.onload = () => {
        const logoSize = canvas.width * 0.24;
        const cx = canvas.width / 2;
        const cy = canvas.height / 2;
        const radius = logoSize / 2 + 4;
        ctx.beginPath();
        ctx.arc(cx, cy, radius, 0, Math.PI * 2);
        ctx.fillStyle = "#ffffff";
        ctx.fill();
        ctx.drawImage(
          logo,
          cx - logoSize / 2,
          cy - logoSize / 2,
          logoSize,
          logoSize,
        );
      };
    },
  );
}

function closeDialog() {
  clearPairTimer();
  show.value = false;
}

watch(show, (val) => {
  if (!val) clearPairTimer();
});

onBeforeUnmount(() => {
  clearPairTimer();
});
</script>

<template>
  <RDialog
    v-model="show"
    :icon="isRegenerate ? 'mdi-refresh' : 'mdi-key-plus'"
    :width="720"
    @close="closeDialog"
  >
    <template #header>
      <span class="r-v2-tok-dialog__title">{{ dialogTitle }}</span>
    </template>

    <template #content>
      <!-- Step 1: Config -->
      <div v-if="step === 'config'" class="r-v2-tok-dialog__body">
        <RTextField
          v-model="tokenName"
          prefix-label="stacked"
          density="comfortable"
          hide-details
        >
          <template #prefix-label>
            <RIcon icon="mdi-tag-outline" size="14" />
            {{ t("settings.client-token-name") }}
          </template>
        </RTextField>
        <RSelect
          v-model="selectedExpiry"
          :items="expiryOptions"
          :label="t('settings.client-token-select-expiry')"
          variant="outlined"
          density="comfortable"
          hide-details
        />
        <div>
          <div class="r-v2-tok-dialog__scopes-title">
            {{ t("settings.client-token-scopes") }}
          </div>
          <div class="r-v2-tok-dialog__scopes-grid">
            <div class="r-v2-tok-dialog__scopes-col">
              <template
                v-for="group in scopeColumns.left"
                :key="`left-${group.label}`"
              >
                <div class="r-v2-tok-dialog__scopes-group">
                  {{ group.label }}
                </div>
                <RCheckbox
                  v-for="scope in group.scopes"
                  :key="scope"
                  :model-value="isScopeSelected(scope)"
                  :label="scope"
                  density="compact"
                  hide-details
                  @update:model-value="(v) => toggleScope(scope, v)"
                />
              </template>
            </div>
            <div class="r-v2-tok-dialog__scopes-col">
              <template
                v-for="group in scopeColumns.right"
                :key="`right-${group.label}`"
              >
                <div class="r-v2-tok-dialog__scopes-group">
                  {{ group.label }}
                </div>
                <RCheckbox
                  v-for="scope in group.scopes"
                  :key="scope"
                  :model-value="isScopeSelected(scope)"
                  :label="scope"
                  density="compact"
                  hide-details
                  @update:model-value="(v) => toggleScope(scope, v)"
                />
              </template>
            </div>
          </div>
        </div>
      </div>

      <!-- Step 2: Delivery -->
      <div
        v-else-if="step === 'delivery'"
        class="r-v2-tok-dialog__body r-v2-tok-dialog__body--center"
      >
        <p class="r-v2-tok-dialog__intro">
          {{
            isRegenerate
              ? "Your previous token has been revoked and a new one generated. Choose how to deliver it:"
              : "Your token has been created. Choose how to deliver it:"
          }}
        </p>
        <p class="r-v2-tok-dialog__warn">
          {{ t("settings.client-token-delivery-hint") }}
        </p>
        <div class="r-v2-tok-dialog__delivery-row">
          <RBtn
            variant="flat"
            size="large"
            prepend-icon="mdi-content-copy"
            @click="step = 'copy'"
          >
            Copy token
          </RBtn>
          <RBtn
            variant="flat"
            size="large"
            prepend-icon="mdi-qrcode"
            @click="startPairing"
          >
            Pair device
          </RBtn>
        </div>
      </div>

      <!-- Step 3: Copy -->
      <div v-else-if="step === 'copy'" class="r-v2-tok-dialog__body">
        <p class="r-v2-tok-dialog__warn">
          {{ t("settings.client-token-delivery-hint") }}
        </p>
        <RTextField
          :model-value="rawToken"
          variant="outlined"
          density="comfortable"
          readonly
          hide-details
          class="r-v2-tok-dialog__token-input"
        >
          <template #append-inner>
            <button
              type="button"
              class="r-v2-tok-dialog__copy-btn"
              :aria-label="t('common.save')"
              @click="copyToken"
            >
              <RIcon icon="mdi-content-copy" size="16" />
            </button>
          </template>
        </RTextField>
      </div>

      <!-- Step 4: Pair -->
      <div
        v-else-if="step === 'pair'"
        class="r-v2-tok-dialog__body r-v2-tok-dialog__body--center"
      >
        <div v-if="pairLoading" class="r-v2-tok-dialog__pair-loading">
          <RProgressCircular indeterminate :size="36" />
        </div>
        <template v-else-if="pairStatus === 'pending'">
          <canvas id="r-v2-pair-qr-code" class="r-v2-tok-dialog__qr" />
          <div class="r-v2-tok-dialog__pair-code">{{ formattedPairCode }}</div>
          <div class="r-v2-tok-dialog__pair-counter">{{ pairCountdown }}s</div>
        </template>
        <template v-else-if="pairStatus === 'claimed'">
          <RIcon
            icon="mdi-check-circle"
            size="64"
            class="r-v2-tok-dialog__pair-ok"
          />
          <p class="r-v2-tok-dialog__pair-result">
            {{ t("settings.client-token-pair-claimed") }}
          </p>
        </template>
        <template v-else>
          <RIcon
            icon="mdi-timer-off"
            size="64"
            class="r-v2-tok-dialog__pair-warn"
          />
          <p class="r-v2-tok-dialog__pair-result">
            {{ t("settings.client-token-pair-expired") }}
          </p>
          <RBtn
            variant="flat"
            prepend-icon="mdi-refresh"
            @click="regeneratePairCode"
          >
            Regenerate code
          </RBtn>
        </template>
      </div>
    </template>

    <template #footer>
      <div class="r-v2-tok-dialog__footer">
        <template v-if="step === 'config'">
          <RBtn variant="text" @click="closeDialog">
            {{ t("common.cancel") }}
          </RBtn>
          <RBtn
            variant="flat"
            color="primary"
            :loading="loading"
            :disabled="!configValid"
            @click="createToken"
          >
            {{ t("common.create") }}
          </RBtn>
        </template>
        <template v-else-if="step === 'delivery'">
          <RBtn variant="text" @click="closeDialog">
            {{ t("common.cancel") }}
          </RBtn>
        </template>
        <template v-else>
          <RBtn variant="text" @click="step = 'delivery'">Back</RBtn>
          <RBtn variant="flat" color="primary" @click="closeDialog">Close</RBtn>
        </template>
      </div>
    </template>
  </RDialog>
</template>

<style scoped>
.r-v2-tok-dialog__title {
  font-weight: var(--r-font-weight-semibold);
}
.r-v2-tok-dialog__body {
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.r-v2-tok-dialog__body--center {
  align-items: center;
  text-align: center;
}

.r-v2-tok-dialog__scopes-title {
  font-size: 11px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--r-color-fg-muted);
  margin-bottom: 10px;
}
.r-v2-tok-dialog__scopes-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
html[data-bp~="xs"] .r-v2-tok-dialog__scopes-grid {
  grid-template-columns: 1fr;
}
.r-v2-tok-dialog__scopes-col {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.r-v2-tok-dialog__scopes-group {
  font-size: 11px;
  font-weight: var(--r-font-weight-semibold);
  color: var(--r-color-fg-muted);
  margin-top: 8px;
  margin-bottom: 4px;
}

.r-v2-tok-dialog__intro {
  margin: 0;
  font-size: 13px;
  color: var(--r-color-fg);
  max-width: 440px;
}
.r-v2-tok-dialog__warn {
  margin: 0;
  font-size: 12px;
  color: var(--r-color-warning);
}

.r-v2-tok-dialog__delivery-row {
  display: flex;
  gap: 12px;
}

.r-v2-tok-dialog__token-input {
  font-family: var(--r-font-family-mono, monospace);
}
.r-v2-tok-dialog__copy-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 28px;
  height: 28px;
  border: none;
  background: transparent;
  color: var(--r-color-brand-primary);
  cursor: pointer;
  border-radius: 6px;
  transition: background var(--r-motion-fast) var(--r-motion-ease-out);
}
.r-v2-tok-dialog__copy-btn:hover {
  background: var(--r-color-surface);
}

.r-v2-tok-dialog__qr {
  display: block;
  margin: 0 auto;
}
.r-v2-tok-dialog__pair-code {
  margin-top: 8px;
  font-family: var(--r-font-family-mono, monospace);
  font-size: 28px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.05em;
  color: var(--r-color-fg);
}
.r-v2-tok-dialog__pair-counter {
  font-size: 12px;
  color: var(--r-color-fg-muted);
}
.r-v2-tok-dialog__pair-loading {
  padding: 32px;
}
.r-v2-tok-dialog__pair-ok {
  color: var(--r-color-success);
}
.r-v2-tok-dialog__pair-warn {
  color: var(--r-color-warning);
}
.r-v2-tok-dialog__pair-result {
  font-size: 14px;
  margin: 4px 0;
  color: var(--r-color-fg);
}

.r-v2-tok-dialog__footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 14px 24px;
  border-top: 1px solid var(--r-color-border);
}
</style>
