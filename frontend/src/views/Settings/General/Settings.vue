<script setup>
import { ref, onBeforeMount } from "vue";
import { useTheme } from "vuetify";
import cronstrue from "cronstrue";
import { themes, autoThemeKey } from "@/styles/themes";
import ThemeOption from "@/views/Settings/General/ThemeOption.vue";
import { api } from "@/services/api";

// Props
const theme = useTheme();
const heartbeat = ref({
  ENABLE_RESCAN_ON_FILESYSTEM_CHANGE: false,
  RESCAN_ON_FILESYSTEM_CHANGE_DELAY: 5,
  ENABLE_SCHEDULED_RESCAN: false,
  SCHEDULED_RESCAN_CRON: "at 03:00 AM, every day",
  ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB: false,
  SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON: "at 03:00 AM, every day",
});

const storedTheme = parseInt(localStorage.getItem("settings.theme"));
const selectedTheme = ref(isNaN(storedTheme) ? autoThemeKey : storedTheme);

// Functions
function toggleTheme() {
  localStorage.setItem("settings.theme", selectedTheme.value);

  const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");
  if (selectedTheme.value === autoThemeKey) {
    theme.global.name.value = mediaMatch.matches ? "dark" : "light";
  } else {
    theme.global.name.value = themes[selectedTheme.value];
  }
}

onBeforeMount(async () => {
  const { data } = await api.get("/heartbeat");
  let rescan = cronstrue.toString(data.SCHEDULED_RESCAN_CRON, {
    verbose: true,
  });
  rescan = rescan.charAt(0).toLocaleLowerCase() + rescan.substr(1);

  let switchUpdate = cronstrue.toString(
    data.SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON,
    { verbose: true }
  );
  switchUpdate =
    switchUpdate.charAt(0).toLocaleLowerCase() + switchUpdate.substr(1);

  let mameUpdate = cronstrue.toString(
    data.SCHEDULED_UPDATE_MAME_XML_CRON,
    { verbose: true }
  );
  mameUpdate = mameUpdate.charAt(0).toLocaleLowerCase() + mameUpdate.substr(1);

  heartbeat.value = {
    ...data,
    SCHEDULED_RESCAN_CRON: rescan,
    SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON: switchUpdate,
    SCHEDULED_UPDATE_MAME_XML_CRON: mameUpdate,
  };
});
</script>
<template>
  <v-card rounded="0">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-brush-variant</v-icon>
        Theme
      </v-toolbar-title>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text>
      <v-item-group
        mandatory
        v-model="selectedTheme"
        @update:model-value="toggleTheme"
      >
        <v-row no-gutters>
          <theme-option
            key="dark"
            value="dark"
            icon="mdi-moon-waning-crescent"
          />
          <theme-option
            key="light"
            value="light"
            icon="mdi-white-balance-sunny"
          />
          <theme-option key="auto" value="auto" icon="mdi-theme-light-dark" />
        </v-row>
      </v-item-group>
    </v-card-text>
  </v-card>

  <v-card rounded="0" class="mt-2">
    <v-toolbar class="bg-terciary" density="compact">
      <v-toolbar-title class="text-button">
        <v-icon class="mr-3">mdi-pulse</v-icon>
        Task Status
      </v-toolbar-title>
    </v-toolbar>

    <v-divider class="border-opacity-25" />

    <v-card-text>
      <v-row>
        <v-col
          cols="12"
          md="4"
          sm="6"
          :class="{
            'status-item d-flex': true,
            disabled: !heartbeat.ENABLE_RESCAN_ON_FILESYSTEM_CHANGE,
          }"
        >
          <v-icon
            :icon="
              heartbeat.ENABLE_RESCAN_ON_FILESYSTEM_CHANGE
                ? 'mdi-file-check-outline'
                : 'mdi-file-remove-outline'
            "
          />
          <div class="ml-3">
            <v-label class="font-weight-bold"
              >Rescan on filesystem change</v-label
            >
            <p class="mt-1">
              Runs a scan when a change is detected in the library path, with a
              {{ heartbeat.RESCAN_ON_FILESYSTEM_CHANGE_DELAY }} minutes delay
            </p>
          </div>
        </v-col>
        <v-col
          cols="12"
          md="4"
          sm="6"
          :class="{
            'status-item d-flex': true,
            disabled: !heartbeat.ENABLE_SCHEDULED_RESCAN,
          }"
        >
          <v-icon
            :icon="
              heartbeat.ENABLE_SCHEDULED_RESCAN
                ? 'mdi-clock-check-outline'
                : 'mdi-clock-remove-outline'
            "
          />
          <div class="ml-3">
            <v-label class="font-weight-bold">Scheduled rescan</v-label>
            <p class="mt-1">
              Rescans the entire library
              {{ heartbeat.SCHEDULED_RESCAN_CRON }}
            </p>
          </div>
        </v-col>
        <v-col
          cols="12"
          md="4"
          sm="6"
          :class="{
            'status-item d-flex': true,
            disabled: !heartbeat.ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB,
          }"
        >
          <v-icon
            :icon="
              heartbeat.ENABLE_SCHEDULED_UPDATE_SWITCH_TITLEDB
                ? 'mdi-clock-check-outline'
                : 'mdi-clock-remove-outline'
            "
          />
          <div class="ml-3">
            <v-label class="font-weight-bold">
              Scheduled Switch TitleDB update
            </v-label>
            <p class="mt-1">
              Updates the Nintedo Switch TitleDB file
              {{ heartbeat.SCHEDULED_UPDATE_SWITCH_TITLEDB_CRON }}
            </p>
          </div>
        </v-col>
        <v-col
          cols="12"
          md="4"
          sm="6"
          :class="{
            'status-item d-flex': true,
            disabled: !heartbeat.ENABLE_SCHEDULED_UPDATE_MAME_XML,
          }"
        >
          <v-icon
            :icon="
              heartbeat.ENABLE_SCHEDULED_UPDATE_MAME_XML
                ? 'mdi-clock-check-outline'
                : 'mdi-clock-remove-outline'
            "
          />
          <div class="ml-3">
            <v-label class="font-weight-bold">
              Scheduled MAME XML update
            </v-label>
            <p class="mt-1">
              Updates the Nintedo MAME XML file
              {{ heartbeat.SCHEDULED_UPDATE_MAME_XML_CRON }}
            </p>
          </div>
        </v-col>
      </v-row>
    </v-card-text>
  </v-card>
</template>

<style scoped>
.status-item.disabled {
  opacity: 0.5;
}
</style>
