<script setup lang="ts">
import axios from "axios";
import { computed, onMounted, ref } from "vue";
import { useRoute } from "vue-router";

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
    errorMessage.value = "No pairing code provided.";
    return;
  }

  if (callback.value) {
    if (!isCustomScheme(callback.value)) {
      status.value = "error";
      errorMessage.value =
        "Only custom URL schemes are supported for callbacks (no http/https).";
      return;
    }

    status.value = "exchanging";
    try {
      const token = await exchange(code.value);
      const separator = callback.value.includes("?") ? "&" : "?";
      window.location.href = `${callback.value}${separator}token=${encodeURIComponent(token)}`;
    } catch (err: any) {
      status.value = "error";
      errorMessage.value =
        err.response?.data?.detail || "Failed to exchange pairing code.";
    }
    return;
  }

  // No callback -- just display the code for manual entry
  status.value = "idle";
});

const formattedCode = computed(() => {
  const c = code.value.replace("-", "").toUpperCase();
  if (c.length === 8) return c.slice(0, 4) + "-" + c.slice(4);
  return c;
});
</script>

<template>
  <v-app>
    <v-main
      class="d-flex align-center justify-center"
      style="min-height: 100dvh"
    >
      <v-card max-width="450" class="pa-8 text-center" variant="outlined">
        <template v-if="status === 'exchanging'">
          <v-progress-circular indeterminate size="48" class="mb-4" />
          <p class="text-body-1">Exchanging pairing code...</p>
        </template>

        <template v-else-if="status === 'error'">
          <v-icon size="64" color="error" class="mb-4">mdi-alert-circle</v-icon>
          <p class="text-body-1">{{ errorMessage }}</p>
        </template>

        <template v-else>
          <v-icon size="48" class="mb-4">mdi-key-variant</v-icon>
          <p class="text-body-1 mb-4">
            Enter this code in your device to complete pairing:
          </p>
          <div
            class="text-h3 font-weight-bold mb-4"
            style="font-family: monospace; letter-spacing: 0.1em"
          >
            {{ formattedCode }}
          </div>
          <p class="text-body-2 text-medium-emphasis">
            This code expires shortly. Return to the web interface to generate a
            new one if needed.
          </p>
        </template>
      </v-card>
    </v-main>
  </v-app>
</template>
