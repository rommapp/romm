<script setup lang="ts">
import { useLocalStorage } from "@vueuse/core";
import semver from "semver";
import { onMounted, ref } from "vue";
import storeHeartbeat from "@/stores/heartbeat";

const heartbeat = storeHeartbeat();
const { VERSION } = heartbeat.value.SYSTEM;
const GITHUB_VERSION = ref(VERSION);
const latestVersionDismissed = ref(VERSION === "development");
const dismissedVersion = useLocalStorage("ui.dismissedVersion", "");

function dismissVersionBanner() {
  dismissedVersion.value = GITHUB_VERSION.value;
  latestVersionDismissed.value = true;
}

async function fetchLatestVersion() {
  try {
    const response = await fetch(
      "https://api.github.com/repos/rommapp/romm/releases/latest",
    );
    const json = await response.json();
    GITHUB_VERSION.value = json.tag_name;

    const publishedAt = new Date(json.published_at);
    latestVersionDismissed.value =
      // Hide if the version is not valid
      !semver.valid(VERSION) ||
      // Hide if the version is the same as the dismissed version
      json.tag_name === dismissedVersion.value ||
      // Hide if the version is less than 2 hours old
      publishedAt.getTime() + 2 * 60 * 60 * 1000 > Date.now();
  } catch (error) {
    console.error("Failed to fetch latest version from Github", error);
  }

  document.removeEventListener("network-quiesced", fetchLatestVersion);
}

function openNewVersion() {
  window.open(
    `https://github.com/rommapp/romm/releases/tag/${GITHUB_VERSION.value}`,
    "_blank",
  );
}

onMounted(async () => {
  document.addEventListener("network-quiesced", fetchLatestVersion);
});
</script>

<template>
  <div v-if="semver.valid(VERSION)" class="pa-3 sticky-bottom">
    <v-slide-y-transition>
      <v-card
        v-if="
          GITHUB_VERSION &&
          semver.gt(GITHUB_VERSION, VERSION) &&
          !latestVersionDismissed
        "
        class="pa-1 border-selected mx-auto"
        max-width="fit-content"
      >
        <v-card-text class="text-center py-2 px-4">
          <span class="text-body-1">New version available:</span>
          <span class="text-primary ml-1 text-body-1 font-weight-medium">{{
            GITHUB_VERSION
          }}</span>
          <v-row class="mt-2 flex justify-center" no-gutters>
            <v-btn-group>
              <v-btn
                density="compact"
                variant="outlined"
                class="pointer"
                size="small"
                @click="dismissVersionBanner"
              >
                Dismiss
              </v-btn>
              <v-btn
                density="compact"
                variant="tonal"
                color="primary"
                size="small"
                @click="openNewVersion"
              >
                See what's new!
              </v-btn>
            </v-btn-group>
          </v-row>
        </v-card-text>
      </v-card>
    </v-slide-y-transition>
  </div>
</template>
<style scoped>
.sticky-bottom {
  position: fixed;
  bottom: 0;
  left: 0;
  width: 100%;
  z-index: 9999;
  pointer-events: none;
}
.sticky-bottom * {
  pointer-events: auto; /* Re-enables pointer events for all child elements */
}
</style>
