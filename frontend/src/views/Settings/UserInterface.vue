<script setup lang="ts">
import ThemeOption from "@/components/Settings/UserInterface/ThemeOption.vue";
import InterfaceOption from "@/components/Settings/UserInterface/InterfaceOption.vue";
import RSection from "@/components/common/RSection.vue";
import { autoThemeKey, themes } from "@/styles/themes";
import { isKeyof } from "@/types";
import { computed, ref } from "vue";
import { useTheme } from "vuetify";
import { isNull } from "lodash";

// Props
const theme = useTheme();
const storedTheme = parseInt(localStorage.getItem("settings.theme") ?? "");
const selectedTheme = ref(isNaN(storedTheme) ? autoThemeKey : storedTheme);
const themeOptions = computed(() => [
  {
    name: "dark",
    icon: "mdi-moon-waning-crescent",
  },
  {
    name: "light",
    icon: "mdi-white-balance-sunny",
  },
  {
    name: "auto",
    icon: "mdi-theme-light-dark",
  },
]);

// Initializing refs from localStorage
const storedGroupRoms = localStorage.getItem("settings.groupRoms");
const groupRomsRef = ref(
  isNull(storedGroupRoms) ? true : storedGroupRoms === "true",
);
const storedSiblings = localStorage.getItem("settings.showSiblings");
const siblingsRef = ref(
  isNull(storedSiblings) ? true : storedSiblings === "true",
);
const storedRegions = localStorage.getItem("settings.showRegions");
const regionsRef = ref(isNull(storedRegions) ? true : storedRegions === "true");
const storedLanguages = localStorage.getItem("settings.showLanguages");
const languagesRef = ref(
  isNull(storedLanguages) ? true : storedLanguages === "true",
);
const storedStatus = localStorage.getItem("settings.showStatus");
const statusRef = ref(isNull(storedStatus) ? true : storedStatus === "true");
const options = computed(() => [
  {
    title: "Group roms",
    description: "Group versions of the same rom together in the gallery",
    iconEnabled: "mdi-group",
    iconDisabled: "mdi-ungroup",
    model: groupRomsRef,
    modelTrigger: toggleGroupRoms,
  },
  {
    title: "Show siblings",
    description:
      'Show siblings count in the gallery when "Group roms" option is enabled',
    iconEnabled: "mdi-account-group-outline",
    iconDisabled: "mdi-account-outline",
    model: siblingsRef,
    disabled: !groupRomsRef.value,
    modelTrigger: toggleSiblings,
  },
  {
    title: "Show regions",
    description: "Show region flags in the gallery",
    iconEnabled: "mdi-flag-outline",
    iconDisabled: "mdi-flag-off-outline",
    model: regionsRef,
    modelTrigger: toggleRegions,
  },
  {
    title: "Show languages",
    description: "Show language flags in the gallery",
    iconEnabled: "mdi-flag-outline",
    iconDisabled: "mdi-flag-off-outline",
    model: languagesRef,
    modelTrigger: toggleLanguages,
  },
  {
    title: "Show status",
    description:
      "Show status icons in the gallery (backlogged, playing, completed, etc)",
    iconEnabled: "mdi-check-circle-outline",
    iconDisabled: "mdi-close-circle-outline",
    model: statusRef,
    modelTrigger: toggleStatus,
  },
]);

// Functions
function toggleTheme() {
  localStorage.setItem("settings.theme", selectedTheme.value.toString());
  const mediaMatch = window.matchMedia("(prefers-color-scheme: dark)");
  if (selectedTheme.value === autoThemeKey) {
    theme.global.name.value = mediaMatch.matches ? "dark" : "light";
  } else if (isKeyof(selectedTheme.value, themes)) {
    theme.global.name.value = themes[selectedTheme.value];
  }
}

// Functions to update localStorage
const toggleGroupRoms = (value: boolean) => {
  groupRomsRef.value = value;
  localStorage.setItem("settings.groupRoms", value.toString());
};

const toggleSiblings = (value: boolean) => {
  siblingsRef.value = value;
  localStorage.setItem("settings.showSiblings", value.toString());
};

const toggleRegions = (value: boolean) => {
  regionsRef.value = value;
  localStorage.setItem("settings.showRegions", value.toString());
};

const toggleLanguages = (value: boolean) => {
  languagesRef.value = value;
  localStorage.setItem("settings.showLanguages", value.toString());
};

const toggleStatus = (value: boolean) => {
  statusRef.value = value;
  localStorage.setItem("settings.showStatus", value.toString());
};
</script>
<template>
  <r-section icon="mdi-brush-variant" title="Theme">
    <template #content>
      <v-item-group
        v-model="selectedTheme"
        mandatory
        @update:model-value="toggleTheme"
      >
        <v-row no-gutters>
          <v-col
            cols="4"
            sm="3"
            md="2"
            class="pa-2"
            v-for="theme in themeOptions"
          >
            <theme-option
              :key="theme.name"
              :text="theme.name"
              :icon="theme.icon"
            />
          </v-col>
        </v-row>
      </v-item-group>
    </template>
  </r-section>

  <r-section icon="mdi-palette-swatch-outline" title="Interface">
    <template #content>
      <v-row no-gutters>
        <v-col cols="12" md="6" v-for="option in options" :key="option.title">
          <interface-option
            class="mx-2"
            :disabled="option.disabled"
            :title="option.title"
            :description="option.description"
            :icon="
              option.model.value ? option.iconEnabled : option.iconDisabled
            "
            v-model="option.model.value"
            @update:model-value="option.modelTrigger"
          />
        </v-col>
      </v-row>
    </template>
  </r-section>
</template>
