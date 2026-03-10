<script setup lang="ts">
import type { Emitter } from "mitt";
import qrcode from "qrcode";
import { computed, inject, nextTick, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import { useDisplay } from "vuetify";
import RDialog from "@/components/common/RDialog.vue";
import clientTokenApi, {
  type ClientTokenSchema,
} from "@/services/api/client-token";
import storeAuth from "@/stores/auth";
import type { Events } from "@/types/emitter";

const emit = defineEmits<{ created: [] }>();

const { t } = useI18n();
const { lgAndUp } = useDisplay();
const auth = storeAuth();
const emitter = inject<Emitter<Events>>("emitter");

const show = ref(false);
const step = ref<"config" | "delivery" | "copy" | "pair">("config");
const loading = ref(false);

const tokenName = ref("");
const selectedScopes = ref<string[]>([]);
const selectedExpiry = ref("never");
const rawToken = ref("");
const tokenId = ref<number | null>(null);

const pairCode = ref("");
const pairExpiresIn = ref(0);
const pairTimer = ref<ReturnType<typeof setInterval> | null>(null);
const pairCountdown = ref(0);
const pairStatus = ref<"pending" | "claimed" | "expired">("pending");
const pairLoading = ref(false);

const isRegenerate = ref(false);
const regenerateToken = ref<ClientTokenSchema | null>(null);

const expiryOptions = [
  { title: t("settings.client-token-expiry-30d"), value: "30d" },
  { title: t("settings.client-token-expiry-90d"), value: "90d" },
  { title: t("settings.client-token-expiry-1y"), value: "1y" },
  { title: t("settings.client-token-expiry-never"), value: "never" },
];

const scopeColumns = computed(() => {
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
    userScopes.value.filter((s) => /^(me|assets|devices|roms\.user)\./.test(s)),
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

  const left: { label: string; scopes: string[] }[] = [];
  if (personal.length > 0) left.push({ label: "Personal", scopes: personal });
  if (admin.length > 0) left.push({ label: "Administration", scopes: admin });
  if (other.length > 0) left.push({ label: "Other", scopes: other });

  const right: { label: string; scopes: string[] }[] = [];
  if (library.length > 0) right.push({ label: "Library", scopes: library });

  return { left, right };
});

const userScopes = computed(() => auth.scopes);
const configValid = computed(
  () => tokenName.value.trim().length > 0 && selectedScopes.value.length > 0,
);

const formattedPairCode = computed(() => {
  if (!pairCode.value) return "";
  const c = pairCode.value;
  return c.slice(0, 4) + "-" + c.slice(4);
});

const dialogTitle = computed(() => {
  if (step.value === "config") return "Create New API Token";
  if (step.value === "delivery") {
    return isRegenerate.value ? "Regenerate Token" : "Deliver Token";
  }
  if (step.value === "copy") return "Copy Token";
  return "Pair Device";
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
  show.value = true;
  step.value = "delivery";
  doRegenerate();
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
  if (pairTimer.value) {
    clearInterval(pairTimer.value);
    pairTimer.value = null;
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
    emitter?.emit("snackbarShow", {
      msg: t("settings.client-token-created"),
      icon: "mdi-check-bold",
      color: "green",
    });
  } catch (error: any) {
    emitter?.emit("snackbarShow", {
      msg: error.response?.data?.detail || "Failed to create token",
      icon: "mdi-close-circle",
      color: "red",
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
    emitter?.emit("snackbarShow", {
      msg: t("settings.client-token-regenerated"),
      icon: "mdi-check-bold",
      color: "green",
    });
  } catch (error: any) {
    emitter?.emit("snackbarShow", {
      msg: error.response?.data?.detail || "Failed to regenerate token",
      icon: "mdi-close-circle",
      color: "red",
    });
    show.value = false;
  } finally {
    loading.value = false;
  }
}

async function copyToken() {
  try {
    await navigator.clipboard.writeText(rawToken.value);
    emitter?.emit("snackbarShow", {
      msg: t("settings.client-token-copied"),
      icon: "mdi-check-bold",
      color: "green",
    });
  } catch {
    // Fallback: select the text
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
    pairExpiresIn.value = data.expires_in;
    pairCountdown.value = data.expires_in;
    pairLoading.value = false;

    await nextTick();
    renderQR(data.code);
    startPairPolling();
  } catch (error: any) {
    pairLoading.value = false;
    emitter?.emit("snackbarShow", {
      msg: error.response?.data?.detail || "Failed to generate pairing code",
      icon: "mdi-close-circle",
      color: "red",
    });
    step.value = "delivery";
  }
}

function startPairPolling() {
  clearPairTimer();
  pairTimer.value = setInterval(async () => {
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
        clearPairTimer();
        if (pairCountdown.value > 0) {
          pairStatus.value = "claimed";
          emitter?.emit("snackbarShow", {
            msg: t("settings.client-token-pair-claimed"),
            icon: "mdi-check-bold",
            color: "green",
          });
        } else {
          pairStatus.value = "expired";
        }
      }
    }
  }, 1000);
}

async function regeneratePairCode() {
  pairStatus.value = "pending";
  pairLoading.value = true;
  try {
    const { data } = await clientTokenApi.pairToken(tokenId.value!);
    pairCode.value = data.code;
    pairExpiresIn.value = data.expires_in;
    pairCountdown.value = data.expires_in;
    pairLoading.value = false;

    await nextTick();
    renderQR(data.code);
    startPairPolling();
  } catch (error: any) {
    pairLoading.value = false;
    emitter?.emit("snackbarShow", {
      msg: error.response?.data?.detail || "Failed to regenerate code",
      icon: "mdi-close-circle",
      color: "red",
    });
  }
}

function renderQR(code: string) {
  const displayCode = code.slice(0, 4) + "-" + code.slice(4);
  const pairUrl = `${window.location.origin}/pair?code=${displayCode}`;
  const canvas = document.getElementById("pair-qr-code") as HTMLCanvasElement;
  if (!canvas) return;

  const size = lgAndUp.value ? 250 : 200;
  qrcode.toCanvas(
    canvas,
    pairUrl,
    {
      margin: 2,
      width: size,
      errorCorrectionLevel: "H",
    },
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

        // Circular white background
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
</script>

<template>
  <RDialog
    v-model="show"
    :icon="isRegenerate ? 'mdi-refresh' : 'mdi-key-plus'"
    :width="lgAndUp ? '50vw' : '95vw'"
    @close="closeDialog"
  >
    <template #header>
      <v-toolbar-title class="ml-2">{{ dialogTitle }}</v-toolbar-title>
    </template>

    <template #content>
      <!-- Step 1: Configuration -->
      <div v-if="step === 'config'" class="pa-4">
        <v-text-field
          v-model="tokenName"
          :label="`${t('settings.client-token-name')} *`"
          variant="outlined"
          density="comfortable"
          class="mb-2"
        />

        <v-select
          v-model="selectedExpiry"
          :label="t('settings.client-token-select-expiry')"
          :items="expiryOptions"
          item-title="title"
          item-value="value"
          variant="outlined"
          density="comfortable"
          class="mb-2"
        />

        <div class="text-subtitle-2 mb-2">
          {{ t("settings.client-token-scopes") }}
        </div>
        <v-row no-gutters>
          <v-col cols="12" md="6" class="pr-2">
            <template v-for="group in scopeColumns.left" :key="group.label">
              <div class="text-caption text-medium-emphasis mb-1 mt-2">
                {{ group.label }}
              </div>
              <v-checkbox
                v-for="scope in group.scopes"
                :key="scope"
                v-model="selectedScopes"
                :label="scope"
                :value="scope"
                density="compact"
                hide-details
              />
            </template>
          </v-col>
          <v-col cols="12" md="6" class="pr-2">
            <template v-for="group in scopeColumns.right" :key="group.label">
              <div class="text-caption text-medium-emphasis mb-1 mt-2">
                {{ group.label }}
              </div>
              <v-checkbox
                v-for="scope in group.scopes"
                :key="scope"
                v-model="selectedScopes"
                :label="scope"
                :value="scope"
                density="compact"
                hide-details
              />
            </template>
          </v-col>
        </v-row>
      </div>

      <!-- Step 2: Delivery method choice -->
      <div v-if="step === 'delivery'" class="pa-4 text-center">
        <p class="text-body-1 mb-2">
          {{
            isRegenerate
              ? "Your previous token has been revoked and a new one generated. Choose how to deliver it:"
              : "Your token has been created. Choose how to deliver it:"
          }}
        </p>
        <p class="text-body-2 mb-4 text-warning">
          {{ t("settings.client-token-delivery-hint") }}
        </p>
        <v-row class="justify-center" no-gutters>
          <v-col cols="auto" class="mx-2">
            <v-btn
              size="large"
              variant="tonal"
              prepend-icon="mdi-content-copy"
              @click="step = 'copy'"
            >
              Copy Token
            </v-btn>
          </v-col>
          <v-col cols="auto" class="mx-2">
            <v-btn
              size="large"
              variant="tonal"
              prepend-icon="mdi-qrcode"
              @click="startPairing"
            >
              Pair Device
            </v-btn>
          </v-col>
        </v-row>
      </div>

      <!-- Step 2a: Copy token -->
      <div v-if="step === 'copy'" class="pa-4">
        <p class="text-body-2 mb-4 text-warning">
          {{ t("settings.client-token-delivery-hint") }}
        </p>
        <v-text-field
          :model-value="rawToken"
          readonly
          variant="outlined"
          density="comfortable"
          style="font-family: monospace"
        >
          <template #append-inner>
            <v-icon
              class="text-primary"
              style="cursor: pointer"
              @click="copyToken"
            >
              mdi-content-copy
            </v-icon>
          </template>
        </v-text-field>
      </div>

      <!-- Step 2b: Pair device -->
      <div v-if="step === 'pair'" class="pa-4 text-center">
        <div v-if="pairLoading" class="py-8">
          <v-progress-circular indeterminate />
        </div>
        <div v-else-if="pairStatus === 'pending'">
          <canvas id="pair-qr-code" class="mx-auto d-block" />
          <div
            class="text-h5 font-weight-bold mt-2"
            style="font-family: monospace"
          >
            {{ formattedPairCode }}
          </div>
          <div class="text-body-2 mt-2">{{ pairCountdown }}s</div>
        </div>
        <div v-else-if="pairStatus === 'claimed'" class="py-8">
          <v-icon size="64" color="green">mdi-check-circle</v-icon>
          <p class="text-h6 mt-4">
            {{ t("settings.client-token-pair-claimed") }}
          </p>
        </div>
        <div v-else-if="pairStatus === 'expired'" class="py-8">
          <v-icon size="64" color="warning">mdi-timer-off</v-icon>
          <p class="text-body-1 mt-4">
            {{ t("settings.client-token-pair-expired") }}
          </p>
          <v-btn
            class="mt-4"
            variant="tonal"
            prepend-icon="mdi-refresh"
            @click="regeneratePairCode"
          >
            Regenerate Code
          </v-btn>
        </div>
      </div>
    </template>

    <template #footer>
      <v-row class="justify-center my-2" no-gutters>
        <v-btn-group divided density="compact">
          <template v-if="step === 'config'">
            <v-btn class="bg-toplayer" @click="closeDialog">
              {{ t("common.cancel") }}
            </v-btn>
            <v-btn
              class="bg-toplayer text-primary"
              :disabled="!configValid"
              :loading="loading"
              @click="createToken"
            >
              {{ t("common.create") }}
            </v-btn>
          </template>

          <template v-else-if="step === 'delivery'">
            <v-btn class="bg-toplayer" @click="closeDialog"> Close </v-btn>
          </template>

          <template v-else-if="step === 'copy'">
            <v-btn class="bg-toplayer" @click="step = 'delivery'"> Back </v-btn>
            <v-btn class="bg-toplayer" @click="closeDialog"> Close </v-btn>
          </template>

          <template v-else-if="step === 'pair'">
            <v-btn class="bg-toplayer" @click="step = 'delivery'"> Back </v-btn>
            <v-btn class="bg-toplayer" @click="closeDialog"> Close </v-btn>
          </template>
        </v-btn-group>
      </v-row>
    </template>
  </RDialog>
</template>
