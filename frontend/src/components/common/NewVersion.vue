<script setup lang="ts">
import storeHeartbeat from "@/stores/heartbeat";
import semver from "semver";
import { onMounted, ref } from "vue";
import { useDisplay } from "vuetify";

// Props
const { mdAndDown } = useDisplay();
const heartbeat = storeHeartbeat();
const { VERSION } = heartbeat.value;
const GITHUB_VERSION = ref(VERSION);
const latestVersionDismissed = ref(VERSION === "development");

// Functions
function dismissVersionBanner() {
  localStorage.setItem("dismissedVersion", GITHUB_VERSION.value);
  latestVersionDismissed.value = true;
}
onMounted(async () => {
  const response = await fetch(
    "https://api.github.com/repos/rommapp/romm/releases/latest"
  );
  const json = await response.json();
  GITHUB_VERSION.value = json.tag_name;
  latestVersionDismissed.value =
    !semver.valid(VERSION) ||
    json.tag_name === localStorage.getItem("dismissedVersion");
});
</script>

<template>
  <v-overlay
    v-if="semver.valid(VERSION)"
    :model-value="true"
    persistent
    no-click-animation
    scroll-strategy="reposition"
    :scrim="false"
    class="justify-start pa-3"
    :class="{ 'ml-16 align-end': !mdAndDown, 'align-start': mdAndDown}"
  >
    <v-slide-y-transition>
      <v-card
        v-if="
          GITHUB_VERSION &&
          semver.gt(GITHUB_VERSION, VERSION) &&
          !latestVersionDismissed
        "
        class="pa-1 border-romm-accent-1"
        rounded="0"
        max-width="344"
      >
        <v-card-text class="py-2 px-4">
          <span class="text-white text-shadow">New version available</span>
          <span class="text-romm-accent-1 ml-1">v{{ GITHUB_VERSION }}</span>
          <v-row class="text-center mt-1" no-gutters>
            <v-col>
              <span class="pointer text-grey" @click="dismissVersionBanner"
                >Dismiss</span
              ><span class="ml-4"
                ><a
                  target="_blank"
                  :href="`https://github.com/rommapp/romm/releases/tag/${GITHUB_VERSION}`"
                  >See what's new!</a
                ></span
              >
            </v-col>
          </v-row>
        </v-card-text>
      </v-card>
    </v-slide-y-transition>
  </v-overlay>
</template>
