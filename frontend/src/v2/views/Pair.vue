<script setup lang="ts">
// Pair — device pairing target. Lands here via a pairing link from a
// native client; either displays the code for manual entry or auto-exchanges
// it and redirects to the client's custom URL scheme.
//
// Ported verbatim from src/views/Pair.vue — the token-exchange flow is the
// contract with the client device and must not drift.
import { RBtn, RIcon } from "@v2/lib";
import axios from "axios";
import { computed, onMounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { useRoute } from "vue-router";

const { t } = useI18n();
const route = useRoute();

const code = computed(() => (route.query.code as string) || "");
const callback = computed(() => (route.query.callback as string) || "");

const status = ref<"idle" | "exchanging" | "error">("idle");
const errorMessage = ref("");

function isCustomScheme(url: string): boolean {
  try {
    const parsed = new URL(url);
    return parsed.protocol !== "http:" && parsed.protocol !== "https:";
  } catch {
    return false;
  }
}

async function exchange(pairCode: string): Promise<string> {
  const resp = await axios.post<{ raw_token: string }>(
    "/api/client-tokens/exchange",
    { code: pairCode },
  );
  return resp.data.raw_token;
}

onMounted(async () => {
  if (!code.value) {
    status.value = "error";
    errorMessage.value = t("settings.pair-no-code");
    return;
  }

  if (callback.value) {
    if (!isCustomScheme(callback.value)) {
      status.value = "error";
      errorMessage.value = t("settings.pair-scheme-error");
      return;
    }

    status.value = "exchanging";
    try {
      const token = await exchange(code.value);
      const separator = callback.value.includes("?") ? "&" : "?";
      window.location.href = `${callback.value}${separator}token=${encodeURIComponent(token)}`;
    } catch (err: unknown) {
      status.value = "error";
      const axiosErr = err as {
        response?: { data?: { detail?: string } };
      };
      errorMessage.value =
        axiosErr.response?.data?.detail ?? t("settings.pair-exchange-failed");
    }
    return;
  }

  status.value = "idle";
});

const formattedCode = computed(() => {
  const c = code.value.replace("-", "").toUpperCase();
  if (c.length === 8) return c.slice(0, 4) + "-" + c.slice(4);
  return c;
});

async function copyCode() {
  try {
    await navigator.clipboard.writeText(formattedCode.value);
  } catch {
    // no-op: clipboard access may be denied
  }
}
</script>

<template>
  <div class="r-v2-pair">
    <div v-if="status === 'exchanging'" class="r-v2-pair__state">
      <div
        class="r-v2-pair__spinner"
        :aria-label="t('settings.pair-exchanging')"
      />
      <p class="r-v2-pair__body">{{ t("settings.pair-exchanging") }}</p>
    </div>

    <div v-else-if="status === 'error'" class="r-v2-pair__state">
      <div class="r-v2-pair__icon-wrap r-v2-pair__icon-wrap--danger">
        <RIcon icon="mdi-alert-circle" size="32" />
      </div>
      <p class="r-v2-pair__body">
        {{ errorMessage }}
      </p>
    </div>

    <div v-else class="r-v2-pair__state">
      <div class="r-v2-pair__icon-wrap">
        <RIcon icon="mdi-key-variant" size="32" />
      </div>
      <p class="r-v2-pair__body">
        {{ t("settings.pair-enter-code-prompt") }}
      </p>
      <div
        class="r-v2-pair__code"
        :aria-label="t('settings.pair-enter-code-prompt')"
      >
        {{ formattedCode }}
      </div>
      <RBtn
        variant="translucent"
        color="primary"
        prepend-icon="mdi-content-copy"
        @click="copyCode"
      >
        {{ t("common.copy-code") }}
      </RBtn>
      <p class="r-v2-pair__hint">
        {{ t("settings.pair-expires-shortly") }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.r-v2-pair {
  background: color-mix(
    in srgb,
    var(--r-color-canvas-bg-deep) 72%,
    transparent
  );
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-lg);
  backdrop-filter: blur(22px);
  -webkit-backdrop-filter: blur(22px);
  padding: 40px 32px;
  box-shadow:
    0 22px 60px color-mix(in srgb, black 55%, transparent),
    0 2px 6px color-mix(in srgb, black 30%, transparent);
}

.r-v2-pair__state {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 16px;
  text-align: center;
}

.r-v2-pair__icon-wrap {
  width: 64px;
  height: 64px;
  border-radius: 50%;
  display: grid;
  place-items: center;
  background: color-mix(in srgb, var(--r-color-brand-primary) 15%, transparent);
  color: var(--r-color-brand-primary);
}
.r-v2-pair__icon-wrap--danger {
  background: color-mix(
    in srgb,
    var(--r-color-status-base-danger) 15%,
    transparent
  );
  color: var(--r-color-danger-fg);
}

.r-v2-pair__body {
  margin: 0;
  color: var(--r-color-fg);
  font-size: var(--r-font-size-md);
  max-width: 320px;
}

.r-v2-pair__code {
  font-family: var(--r-font-family-mono, monospace);
  font-size: 40px;
  font-weight: var(--r-font-weight-bold);
  letter-spacing: 0.14em;
  color: var(--r-color-fg);
  background: var(--r-color-surface);
  border: 1px solid var(--r-color-border-strong);
  border-radius: var(--r-radius-md);
  padding: 18px 28px;
  margin: 4px 0;
  user-select: all;
}

.r-v2-pair__hint {
  margin: 4px 0 0;
  color: var(--r-color-fg-muted);
  font-size: var(--r-font-size-sm);
  max-width: 360px;
}

.r-v2-pair__spinner {
  width: 48px;
  height: 48px;
  border-radius: 50%;
  border: 3px solid var(--r-color-surface-hover);
  border-top-color: var(--r-color-brand-primary);
  animation: r-v2-pair-spin 0.8s linear infinite;
}
@keyframes r-v2-pair-spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
